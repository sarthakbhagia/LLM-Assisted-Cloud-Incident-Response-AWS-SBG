#!/usr/bin/env python3
"""
Full End-to-End Incident Flow Test
Triggers a real incident and tests the complete pipeline flow.
"""
import json
import time
import uuid
import boto3
import requests
import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FullIncidentFlowTest:
    def __init__(self):
        self.session = boto3.Session()
        self.lambda_client = self.session.client('lambda')
        self.dynamodb = self.session.client('dynamodb')
        self.s3 = self.session.client('s3')
        self.cloudwatch = self.session.client('cloudwatch')
        
        # Get account ID at runtime (not hardcoded)
        self.account_id = self.session.client('sts').get_caller_identity()['Account']
        self.region = self.session.region_name or os.environ.get('AWS_REGION', 'ap-south-1')
        
        # Configuration - use env vars with defaults for dev environment
        self.environment = os.environ.get('ENVIRONMENT', 'dev')
        self.incidents_table = os.environ.get('INCIDENTS_TABLE', f'incidents-{self.environment}')
        self.data_lake_bucket = os.environ.get('DATA_LAKE_BUCKET', f'llm-incident-datalake-{self.account_id}-{self.environment}')
        self.service_a_url = os.environ.get('SERVICE_A_URL', f'https://0jqdaxn8k1.execute-api.{self.region}.amazonaws.com/Prod/start')
        
    def trigger_resource_exhaustion(self):
        """Trigger a resource exhaustion scenario by making many rapid requests"""
        logger.info("Triggering resource exhaustion scenario...")
        
        # Make many concurrent requests to trigger the alarm
        for i in range(10):
            try:
                response = requests.get(self.service_a_url, timeout=5)
                logger.info(f"Request {i+1}: Status {response.status_code}")
                time.sleep(0.1)  # Small delay between requests
            except Exception as e:
                logger.info(f"Request {i+1} failed (expected): {e}")
                
        logger.info("Resource exhaustion trigger completed")
        
    def wait_for_alarm_trigger(self, alarm_name, timeout=300):
        """Wait for CloudWatch alarm to trigger"""
        logger.info(f"Waiting for alarm {alarm_name} to trigger...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = self.cloudwatch.describe_alarms(AlarmNames=[alarm_name])
                if response['MetricAlarms']:
                    alarm_state = response['MetricAlarms'][0]['StateValue']
                    logger.info(f"Alarm state: {alarm_state}")
                    
                    if alarm_state == 'ALARM':
                        logger.info("✓ Alarm triggered successfully")
                        return True
                        
            except Exception as e:
                logger.error(f"Error checking alarm: {e}")
                
            time.sleep(10)  # Check every 10 seconds
            
        logger.error("✗ Alarm did not trigger within timeout")
        return False
        
    def wait_for_incident_record(self, timeout=300):
        """Wait for an incident record to appear in DynamoDB"""
        logger.info("Waiting for incident record to be created...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Scan for recent incidents
                response = self.dynamodb.scan(
                    TableName=self.incidents_table,
                    FilterExpression='fault_class = :fc',
                    ExpressionAttributeValues={
                        ':fc': {'S': 'resource_exhaustion'}
                    }
                )
                
                if response['Items']:
                    # Get the most recent incident
                    incidents = sorted(response['Items'], 
                                     key=lambda x: x['detected_at']['S'], 
                                     reverse=True)
                    latest_incident = incidents[0]
                    
                    logger.info(f"✓ Found incident: {latest_incident['incident_id']['S']}")
                    return latest_incident['incident_id']['S']
                    
            except Exception as e:
                logger.error(f"Error checking for incidents: {e}")
                
            time.sleep(10)
            
        logger.error("✗ No incident record found within timeout")
        return None
        
    def check_incident_pipeline_progress(self, incident_id, timeout=600):
        """Monitor the incident through the complete pipeline"""
        logger.info(f"Monitoring incident {incident_id} through pipeline...")
        
        stages = [
            'detected',
            'evidence_collected', 
            'diagnosed',
            'pending_approval',
            'approved',
            'executed',
            'verified'
        ]
        
        completed_stages = set()
        start_time = time.time()
        
        while time.time() - start_time < timeout and len(completed_stages) < len(stages):
            try:
                # Get incident record
                response = self.dynamodb.get_item(
                    TableName=self.incidents_table,
                    Key={'incident_id': {'S': incident_id}}
                )
                
                if 'Item' in response:
                    incident = response['Item']
                    
                    # Check various stages
                    if incident.get('raw_data_s3_key') and 'evidence_collected' not in completed_stages:
                        logger.info("✓ Stage: Evidence collected")
                        completed_stages.add('evidence_collected')
                        
                    if incident.get('diagnosis', {}).get('M', {}).get('root_cause') and 'diagnosed' not in completed_stages:
                        logger.info("✓ Stage: Diagnosis completed")
                        logger.info(f"  Root cause: {incident['diagnosis']['M']['root_cause']['S']}")
                        logger.info(f"  Confidence: {incident['diagnosis']['M']['confidence']['N']}")
                        completed_stages.add('diagnosed')
                        
                    remediation_status = incident.get('remediation', {}).get('M', {}).get('status', {}).get('S', '')
                    if remediation_status == 'pending_approval' and 'pending_approval' not in completed_stages:
                        logger.info("✓ Stage: Pending approval")
                        completed_stages.add('pending_approval')
                        
                    if remediation_status == 'approved' and 'approved' not in completed_stages:
                        logger.info("✓ Stage: Approved")
                        completed_stages.add('approved')
                        
                    if remediation_status == 'executed' and 'executed' not in completed_stages:
                        logger.info("✓ Stage: Remediation executed")
                        completed_stages.add('executed')
                        
                    verification_status = incident.get('verification', {}).get('M', {}).get('status', {}).get('S', '')
                    if verification_status in ['resolved', 'not_resolved', 'inconclusive'] and 'verified' not in completed_stages:
                        logger.info(f"✓ Stage: Verification completed - {verification_status}")
                        completed_stages.add('verified')
                        
                    # Print current status
                    logger.info(f"Pipeline progress: {len(completed_stages)}/{len(stages)} stages completed")
                    
            except Exception as e:
                logger.error(f"Error monitoring pipeline: {e}")
                
            time.sleep(15)  # Check every 15 seconds
            
        return completed_stages
        
    def approve_incident(self, incident_id):
        """Manually approve the incident for remediation"""
        logger.info(f"Approving incident {incident_id} for remediation...")
        
        try:
            # Update incident status to approved
            self.dynamodb.update_item(
                TableName=self.incidents_table,
                Key={'incident_id': {'S': incident_id}},
                UpdateExpression='SET remediation.#status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': {'S': 'approved'}}
            )
            
            # Invoke remediation Lambda - use naming convention to construct function name
            remediation_function = f'llm-incident-response-{self.environment}-RemediationFunction'
            
            response = self.lambda_client.invoke(
                FunctionName=remediation_function,
                InvocationType='Event',  # Async
                Payload=json.dumps({'incident_id': incident_id})
            )
            
            logger.info("✓ Incident approved and remediation triggered")
            return True
            
        except Exception as e:
            logger.error(f"✗ Error approving incident: {e}")
            return False
            
    def run_full_test(self):
        """Run the complete end-to-end test"""
        logger.info("Starting Full End-to-End Incident Flow Test")
        logger.info("=" * 60)
        
        # Step 1: Trigger resource exhaustion
        self.trigger_resource_exhaustion()
        
        # Step 2: Wait for alarm to trigger  
        alarm_name = "incident-service-a-resource-exhaustion-dev"
        if not self.wait_for_alarm_trigger(alarm_name):
            logger.error("Test failed: Alarm did not trigger")
            return False
            
        # Step 3: Wait for incident record
        incident_id = self.wait_for_incident_record()
        if not incident_id:
            logger.error("Test failed: No incident record created")
            return False
            
        # Step 4: Monitor initial pipeline stages (detection -> collection -> diagnosis)
        logger.info("Monitoring automatic pipeline stages...")
        time.sleep(30)  # Give system time to process
        
        completed_stages = self.check_incident_pipeline_progress(incident_id, timeout=180)
        
        # Step 5: Approve incident if it reached pending approval
        if 'pending_approval' in completed_stages or 'diagnosed' in completed_stages:
            if self.approve_incident(incident_id):
                # Step 6: Monitor remediation and verification stages
                logger.info("Monitoring remediation and verification...")
                final_stages = self.check_incident_pipeline_progress(incident_id, timeout=300)
                completed_stages.update(final_stages)
            
        # Step 7: Generate final report
        logger.info("=" * 60)
        logger.info("FULL E2E TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Incident ID: {incident_id}")
        logger.info(f"Completed Stages: {len(completed_stages)}/7")
        
        for stage in ['evidence_collected', 'diagnosed', 'pending_approval', 'approved', 'executed', 'verified']:
            status = "✓" if stage in completed_stages else "✗"
            logger.info(f"{status} {stage}")
            
        success_rate = len(completed_stages) / 7 * 100
        logger.info(f"\nOverall Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 85:
            logger.info("✓ FULL E2E TEST PASSED")
            return True
        else:
            logger.error("✗ FULL E2E TEST FAILED")
            return False

def main():
    test = FullIncidentFlowTest()
    success = test.run_full_test()
    exit(0 if success else 1)

if __name__ == "__main__":
    main()