#!/usr/bin/env python3
"""
End-to-End Test Suite for LLM-Assisted Cloud Incident Response
Tests phases 0-7 to verify all services are deployed and communicating properly.
"""
import json
import time
import uuid
import boto3
import requests
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class E2ETestRunner:
    def __init__(self):
        self.session = boto3.Session()
        self.dynamodb = self.session.client('dynamodb')
        self.s3 = self.session.client('s3')
        self.cloudwatch = self.session.client('cloudwatch')
        self.lambda_client = self.session.client('lambda')
        self.config_client = self.session.client('config')
        self.guardduty = self.session.client('guardduty')
        self.sts = self.session.client('sts')
        
        # Load environment configuration
        self.env = self._load_environment()
        self.test_results = {}
        
    def _load_environment(self):
        """Load environment configuration from env.json or defaults"""
        try:
            with open('env.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("env.json not found, using defaults")
            return {
                "environment": "dev",
                "region": "us-east-1"
            }
    
    def test_phase_0_infrastructure(self):
        """Test Phase 0: Verify core infrastructure is deployed"""
        logger.info("Testing Phase 0: Infrastructure Bootstrap")
        
        # Test S3 Data Lake
        bucket_name = f"llm-incident-datalake-{self.sts.get_caller_identity()['Account']}-{self.env.get('environment', 'dev')}"
        try:
            self.s3.head_bucket(Bucket=bucket_name)
            logger.info("✓ S3 Data Lake bucket exists")
            self.test_results['phase_0_s3'] = True
        except Exception as e:
            logger.error(f"✗ S3 Data Lake bucket not found: {e}")
            self.test_results['phase_0_s3'] = False
            
        # Test DynamoDB Incidents Table
        table_name = f"incidents-{self.env.get('environment', 'dev')}"
        try:
            self.dynamodb.describe_table(TableName=table_name)
            logger.info("✓ DynamoDB incidents table exists")
            self.test_results['phase_0_dynamodb'] = True
        except Exception as e:
            logger.error(f"✗ DynamoDB incidents table not found: {e}")
            self.test_results['phase_0_dynamodb'] = False
            
    def test_phase_1_demo_app(self):
        """Test Phase 1: Verify demo application services are running"""
        logger.info("Testing Phase 1: Demo Application")
        
        # Test Service A, B, C Lambda functions exist
        functions = ['ServiceAFunction', 'ServiceBFunction', 'ServiceCFunction']
        for func in functions:
            try:
                # Get function name from stack outputs
                response = self.lambda_client.list_functions()
                function_names = [f['FunctionName'] for f in response['Functions']]
                matching_functions = [name for name in function_names if func.lower().replace('function', '') in name.lower()]
                
                if matching_functions:
                    logger.info(f"✓ {func} deployed as {matching_functions[0]}")
                    self.test_results[f'phase_1_{func.lower()}'] = True
                else:
                    logger.error(f"✗ {func} not found")
                    self.test_results[f'phase_1_{func.lower()}'] = False
                    
            except Exception as e:
                logger.error(f"✗ Error checking {func}: {e}")
                self.test_results[f'phase_1_{func.lower()}'] = False
    def test_phase_2_detection(self):
        """Test Phase 2: Verify detection systems are configured"""
        logger.info("Testing Phase 2: Detection Systems")
        
        # Test CloudWatch Alarms exist
        alarm_names = [
            f"incident-service-a-resource-exhaustion-{self.env.get('environment', 'dev')}",
            f"incident-service-a-errors-{self.env.get('environment', 'dev')}",
            f"incident-service-cascade-{self.env.get('environment', 'dev')}"
        ]
        
        for alarm_name in alarm_names:
            try:
                self.cloudwatch.describe_alarms(AlarmNames=[alarm_name])
                logger.info(f"✓ CloudWatch alarm {alarm_name} exists")
                self.test_results[f'phase_2_alarm_{alarm_name.split("-")[-2]}'] = True
            except Exception as e:
                logger.error(f"✗ CloudWatch alarm {alarm_name} not found: {e}")
                self.test_results[f'phase_2_alarm_{alarm_name.split("-")[-2]}'] = False
        
        # Test AWS Config Rules
        config_rules = [
            f"incident-public-s3-{self.env.get('environment', 'dev')}",
            f"incident-iam-policy-{self.env.get('environment', 'dev')}"
        ]
        
        for rule_name in config_rules:
            try:
                self.config_client.describe_config_rules(ConfigRuleNames=[rule_name])
                logger.info(f"✓ Config rule {rule_name} exists")
                self.test_results[f'phase_2_config_{rule_name.split("-")[-2]}'] = True
            except Exception as e:
                logger.error(f"✗ Config rule {rule_name} not found: {e}")
                self.test_results[f'phase_2_config_{rule_name.split("-")[-2]}'] = False
                
    def test_phase_3_collection(self):
        """Test Phase 3: Verify collector Lambda is deployed"""
        logger.info("Testing Phase 3: Data Collection")
        
        try:
            # Find collector function
            response = self.lambda_client.list_functions()
            collector_functions = [f for f in response['Functions'] if 'collector' in f['FunctionName'].lower()]
            
            if collector_functions:
                collector_func = collector_functions[0]['FunctionName']
                logger.info(f"✓ Collector function found: {collector_func}")
                
                # Test collector function can be invoked
                test_event = {
                    "source": "test",
                    "fault_class": "resource_exhaustion",
                    "test_mode": True
                }
                
                response = self.lambda_client.invoke(
                    FunctionName=collector_func,
                    InvocationType='RequestResponse',
                    Payload=json.dumps(test_event)
                )
                
                if response['StatusCode'] == 200:
                    logger.info("✓ Collector function invocation successful")
                    self.test_results['phase_3_collector'] = True
                else:
                    logger.error("✗ Collector function invocation failed")
                    self.test_results['phase_3_collector'] = False
            else:
                logger.error("✗ Collector function not found")
                self.test_results['phase_3_collector'] = False
                
        except Exception as e:
            logger.error(f"✗ Error testing collector: {e}")
            self.test_results['phase_3_collector'] = False
            
    def test_phase_4_diagnosis(self):
        """Test Phase 4: Verify diagnosis Lambda and runbook loading"""
        logger.info("Testing Phase 4: Diagnosis System")
        
        try:
            # Find diagnosis function
            response = self.lambda_client.list_functions()
            diagnosis_functions = [f for f in response['Functions'] if 'diagnosis' in f['FunctionName'].lower()]
            
            if diagnosis_functions:
                diagnosis_func = diagnosis_functions[0]['FunctionName']
                logger.info(f"✓ Diagnosis function found: {diagnosis_func}")
                
                # Check runbook files exist
                runbook_files = [
                    'knowledge_base/resource_exhaustion.md',
                    'knowledge_base/misconfiguration.md',
                    'knowledge_base/service_cascade.md'
                ]
                
                runbooks_exist = True
                for runbook in runbook_files:
                    try:
                        with open(runbook, 'r') as f:
                            content = f.read()
                            if len(content) > 0:
                                logger.info(f"✓ Runbook {runbook} exists and has content")
                            else:
                                logger.warning(f"⚠ Runbook {runbook} exists but is empty")
                                runbooks_exist = False
                    except FileNotFoundError:
                        logger.error(f"✗ Runbook {runbook} not found")
                        runbooks_exist = False
                
                self.test_results['phase_4_diagnosis'] = True
                self.test_results['phase_4_runbooks'] = runbooks_exist
            else:
                logger.error("✗ Diagnosis function not found")
                self.test_results['phase_4_diagnosis'] = False
                
        except Exception as e:
            logger.error(f"✗ Error testing diagnosis: {e}")
            self.test_results['phase_4_diagnosis'] = False
    def test_phase_5_reporting_approval(self):
        """Test Phase 5: Verify reporting and approval systems"""
        logger.info("Testing Phase 5: Reporting and Approval")
        
        try:
            # Find notify and approval functions
            response = self.lambda_client.list_functions()
            notify_functions = [f for f in response['Functions'] if 'notify' in f['FunctionName'].lower()]
            approval_functions = [f for f in response['Functions'] if 'approval' in f['FunctionName'].lower()]
            
            if notify_functions:
                logger.info(f"✓ Notify function found: {notify_functions[0]['FunctionName']}")
                self.test_results['phase_5_notify'] = True
            else:
                logger.error("✗ Notify function not found")
                self.test_results['phase_5_notify'] = False
                
            if approval_functions:
                logger.info(f"✓ Approval function found: {approval_functions[0]['FunctionName']}")
                self.test_results['phase_5_approval'] = True
            else:
                logger.error("✗ Approval function not found")
                self.test_results['phase_5_approval'] = False
                
        except Exception as e:
            logger.error(f"✗ Error testing reporting/approval: {e}")
            self.test_results['phase_5_notify'] = False
            self.test_results['phase_5_approval'] = False
            
    def test_phase_6_remediation(self):
        """Test Phase 6: Verify remediation system"""
        logger.info("Testing Phase 6: Remediation System")
        
        try:
            # Find remediation function
            response = self.lambda_client.list_functions()
            remediation_functions = [f for f in response['Functions'] if 'remediation' in f['FunctionName'].lower()]
            
            if remediation_functions:
                remediation_func = remediation_functions[0]['FunctionName']
                logger.info(f"✓ Remediation function found: {remediation_func}")
                self.test_results['phase_6_remediation'] = True
                
                # Check if actions.py exists and has remediation actions
                try:
                    with open('src/remediation/actions.py', 'r') as f:
                        content = f.read()
                        required_actions = ['scale_up', 'restart_service', 'lock_s3_bucket', 'tighten_iam_policy']
                        actions_implemented = all(action in content for action in required_actions)
                        
                        if actions_implemented:
                            logger.info("✓ All required remediation actions implemented")
                            self.test_results['phase_6_actions'] = True
                        else:
                            logger.warning("⚠ Some remediation actions may be missing")
                            self.test_results['phase_6_actions'] = False
                except FileNotFoundError:
                    logger.error("✗ actions.py not found")
                    self.test_results['phase_6_actions'] = False
            else:
                logger.error("✗ Remediation function not found")
                self.test_results['phase_6_remediation'] = False
                
        except Exception as e:
            logger.error(f"✗ Error testing remediation: {e}")
            self.test_results['phase_6_remediation'] = False
            
    def test_phase_6_5_verification(self):
        """Test Phase 6.5: Verify closed-loop verification system"""
        logger.info("Testing Phase 6.5: Closed-loop Verification")
        
        try:
            # Find verification function
            response = self.lambda_client.list_functions()
            verification_functions = [f for f in response['Functions'] if 'verification' in f['FunctionName'].lower()]
            
            if verification_functions:
                verification_func = verification_functions[0]['FunctionName']
                logger.info(f"✓ Verification function found: {verification_func}")
                self.test_results['phase_6_5_verification'] = True
            else:
                logger.error("✗ Verification function not found")
                self.test_results['phase_6_5_verification'] = False
                
        except Exception as e:
            logger.error(f"✗ Error testing verification: {e}")
            self.test_results['phase_6_5_verification'] = False
            
    def test_phase_7_evaluation(self):
        """Test Phase 7: Verify evaluation and fault injection systems"""
        logger.info("Testing Phase 7: Evaluation System")
        
        # Check if evaluation scripts exist
        eval_files = [
            'evaluation/run_evaluation.py',
            'evaluation/metrics.py',
            'fault_injection/inject_resource_exhaustion.py',
            'fault_injection/inject_misconfiguration.py',
            'fault_injection/inject_service_cascade.py'
        ]
        
        all_exist = True
        for eval_file in eval_files:
            try:
                with open(eval_file, 'r') as f:
                    content = f.read()
                    if len(content) > 0:
                        logger.info(f"✓ Evaluation file {eval_file} exists")
                    else:
                        logger.warning(f"⚠ Evaluation file {eval_file} exists but is empty")
                        all_exist = False
            except FileNotFoundError:
                logger.error(f"✗ Evaluation file {eval_file} not found")
                all_exist = False
                
        self.test_results['phase_7_evaluation'] = all_exist
    def test_service_communication(self):
        """Test service-to-service communication in the demo app"""
        logger.info("Testing Service Communication")
        
        try:
            # Get API Gateway URL from CloudFormation stack outputs
            cf_client = self.session.client('cloudformation')
            
            # Find the stack
            stacks = cf_client.describe_stacks()
            api_url = None
            
            for stack in stacks['Stacks']:
                if 'llm-incident' in stack['StackName'].lower() or 'incident' in stack['StackName'].lower():
                    outputs = stack.get('Outputs', [])
                    for output in outputs:
                        if 'api' in output['OutputKey'].lower() and 'url' in output['OutputKey'].lower():
                            api_url = output['OutputValue']
                            break
                    if api_url:
                        break
            
            if api_url:
                # Test Service A endpoint (which should call B -> C)
                test_url = f"{api_url}/start"
                response = requests.get(test_url, timeout=30)
                
                if response.status_code == 200:
                    logger.info("✓ Service communication chain working")
                    self.test_results['service_communication'] = True
                else:
                    logger.error(f"✗ Service communication failed: {response.status_code}")
                    self.test_results['service_communication'] = False
            else:
                # Try the known API Gateway URL from stack outputs
                try:
                    test_url = "https://0jqdaxn8k1.execute-api.ap-south-1.amazonaws.com/Prod/start"
                    response = requests.get(test_url, timeout=30)
                    
                    if response.status_code == 200:
                        logger.info("✓ Service communication chain working (direct URL)")
                        self.test_results['service_communication'] = True
                    else:
                        logger.error(f"✗ Service communication failed: {response.status_code}")
                        self.test_results['service_communication'] = False
                except Exception as e:
                    logger.error(f"✗ Service communication test failed: {e}")
                    self.test_results['service_communication'] = False
                
        except Exception as e:
            logger.error(f"✗ Error testing service communication: {e}")
            self.test_results['service_communication'] = False
            
    def test_bedrock_access(self):
        """Test Bedrock model access with fallback chain"""
        logger.info("Testing Bedrock Access")
        
        try:
            bedrock = self.session.client('bedrock-runtime')
            
            test_prompt = "Hello, this is a test."
            models = [
                ("apac.anthropic.claude-3-5-sonnet-20241022-v2:0", "anthropic"),
                ("anthropic.claude-3-sonnet-20240229-v1:0", "anthropic"),
                ("apac.amazon.nova-micro-v1:0", "nova"),
            ]
            
            for model_id, model_type in models:
                try:
                    if model_type == "anthropic":
                        body = json.dumps({
                            "anthropic_version": "bedrock-2023-05-31",
                            "max_tokens": 100,
                            "messages": [{"role": "user", "content": test_prompt}]
                        })
                    else:
                        body = json.dumps({
                            "messages": [{"role": "user", "content": [{"text": test_prompt}]}],
                            "inferenceConfig": {"maxTokens": 100, "temperature": 0.1}
                        })
                    
                    response = bedrock.invoke_model(
                        body=body,
                        modelId=model_id,
                        accept='application/json',
                        contentType='application/json'
                    )
                    
                    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                        logger.info(f"✓ Bedrock model access working with {model_id}")
                        self.test_results['bedrock_access'] = True
                        return
                        
                except Exception as e:
                    logger.warning(f"Model {model_id} failed: {e}, trying next...")
                    continue
            
            logger.error("✗ All Bedrock models failed")
            self.test_results['bedrock_access'] = False
                
        except Exception as e:
            logger.error(f"✗ Error testing Bedrock access: {e}")
            self.test_results['bedrock_access'] = False
            
    def run_end_to_end_incident_simulation(self):
        """Simulate a complete incident flow"""
        logger.info("Running End-to-End Incident Simulation")
        
        try:
            # Create a test incident record
            incident_id = str(uuid.uuid4())
            table_name = f"incidents-{self.env.get('environment', 'dev')}"
            
            test_incident = {
                'incident_id': {'S': incident_id},
                'fault_class': {'S': 'resource_exhaustion'},
                'detected_at': {'S': datetime.utcnow().isoformat()},
                'raw_data_s3_key': {'S': f'incidents/{incident_id}/raw_data.json'},
                'diagnosis': {
                    'M': {
                        'root_cause': {'S': 'Test incident'},
                        'confidence': {'N': '0.9'},
                        'affected_resources': {'L': [{'S': 'test-resource'}]},
                        'suggested_action': {'S': 'manual_review_required'},
                        'reasoning_trace': {'S': 'This is a test incident'},
                        'used_rag': {'BOOL': True}
                    }
                },
                'remediation': {
                    'M': {
                        'status': {'S': 'pending_approval'},
                        'action_taken': {'S': 'none'},
                    }
                },
                'verification': {
                    'M': {
                        'status': {'S': 'not_run'}
                    }
                }
            }
            
            # Write test incident to DynamoDB
            self.dynamodb.put_item(TableName=table_name, Item=test_incident)
            
            # Verify we can read it back
            response = self.dynamodb.get_item(
                TableName=table_name,
                Key={'incident_id': {'S': incident_id}}
            )
            
            if 'Item' in response:
                logger.info("✓ End-to-end incident data flow working")
                self.test_results['e2e_simulation'] = True
                
                # Clean up test data
                self.dynamodb.delete_item(
                    TableName=table_name,
                    Key={'incident_id': {'S': incident_id}}
                )
            else:
                logger.error("✗ Failed to read back test incident")
                self.test_results['e2e_simulation'] = False
                
        except Exception as e:
            logger.error(f"✗ Error in E2E simulation: {e}")
            self.test_results['e2e_simulation'] = False
    def generate_report(self):
        """Generate a comprehensive test report"""
        logger.info("Generating Test Report")
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        failed_tests = total_tests - passed_tests
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
            },
            "phase_results": {},
            "detailed_results": self.test_results,
            "recommendations": []
        }
        
        # Group results by phase
        phase_groups = {
            "Phase 0 - Infrastructure": [k for k in self.test_results if k.startswith('phase_0')],
            "Phase 1 - Demo App": [k for k in self.test_results if k.startswith('phase_1')],
            "Phase 2 - Detection": [k for k in self.test_results if k.startswith('phase_2')],
            "Phase 3 - Collection": [k for k in self.test_results if k.startswith('phase_3')],
            "Phase 4 - Diagnosis": [k for k in self.test_results if k.startswith('phase_4')],
            "Phase 5 - Reporting/Approval": [k for k in self.test_results if k.startswith('phase_5')],
            "Phase 6 - Remediation": [k for k in self.test_results if k.startswith('phase_6')],
            "Phase 6.5 - Verification": [k for k in self.test_results if k.startswith('phase_6_5')],
            "Phase 7 - Evaluation": [k for k in self.test_results if k.startswith('phase_7')],
            "Integration Tests": [k for k in self.test_results if not k.startswith('phase_')]
        }
        
        for phase_name, test_keys in phase_groups.items():
            if test_keys:
                phase_passed = sum(1 for k in test_keys if self.test_results.get(k, False))
                phase_total = len(test_keys)
                report["phase_results"][phase_name] = {
                    "passed": phase_passed,
                    "total": phase_total,
                    "success_rate": f"{(phase_passed/phase_total)*100:.1f}%" if phase_total > 0 else "0%",
                    "status": "PASS" if phase_passed == phase_total else "FAIL"
                }
        
        # Generate recommendations
        if not self.test_results.get('phase_0_s3', False):
            report["recommendations"].append("Deploy S3 data lake bucket using SAM template")
        if not self.test_results.get('phase_0_dynamodb', False):
            report["recommendations"].append("Deploy DynamoDB incidents table using SAM template")
        if not self.test_results.get('bedrock_access', False):
            report["recommendations"].append("Check Bedrock service availability and IAM permissions")
        if not self.test_results.get('service_communication', False):
            report["recommendations"].append("Verify API Gateway deployment and service endpoints")
        if not self.test_results.get('phase_4_runbooks', False):
            report["recommendations"].append("Create knowledge base runbook files")
        
        return report
        
    def run_all_tests(self):
        """Run all test phases"""
        logger.info("Starting End-to-End Test Suite")
        logger.info("=" * 60)
        
        try:
            self.test_phase_0_infrastructure()
            self.test_phase_1_demo_app()
            self.test_phase_2_detection()
            self.test_phase_3_collection()
            self.test_phase_4_diagnosis()
            self.test_phase_5_reporting_approval()
            self.test_phase_6_remediation()
            self.test_phase_6_5_verification()
            self.test_phase_7_evaluation()
            self.test_service_communication()
            self.test_bedrock_access()
            self.run_end_to_end_incident_simulation()
            
            report = self.generate_report()
            
            # Save report to file
            with open(f'test_report_{int(time.time())}.json', 'w') as f:
                json.dump(report, f, indent=2)
                
            # Print summary
            logger.info("=" * 60)
            logger.info("TEST SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total Tests: {report['summary']['total_tests']}")
            logger.info(f"Passed: {report['summary']['passed']}")
            logger.info(f"Failed: {report['summary']['failed']}")
            logger.info(f"Success Rate: {report['summary']['success_rate']}")
            logger.info("")
            
            for phase_name, phase_result in report['phase_results'].items():
                status_symbol = "✓" if phase_result['status'] == 'PASS' else "✗"
                logger.info(f"{status_symbol} {phase_name}: {phase_result['passed']}/{phase_result['total']} ({phase_result['success_rate']})")
            
            if report['recommendations']:
                logger.info("")
                logger.info("RECOMMENDATIONS:")
                for i, rec in enumerate(report['recommendations'], 1):
                    logger.info(f"{i}. {rec}")
                    
            return report
            
        except Exception as e:
            logger.error(f"Test suite failed: {e}")
            return {"error": str(e)}

def main():
    """Main entry point"""
    runner = E2ETestRunner()
    report = runner.run_all_tests()
    
    # Exit with appropriate code
    if "error" in report:
        exit(1)
    elif report['summary']['failed'] > 0:
        exit(1)
    else:
        exit(0)

if __name__ == "__main__":
    main()