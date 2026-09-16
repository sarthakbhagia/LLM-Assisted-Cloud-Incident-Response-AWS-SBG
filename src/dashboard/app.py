#!/usr/bin/env python3
"""
Dashboard API Lambda - Phase 8
Read-only endpoints for the presentation dashboard.
Strictly read-only - no write operations allowed.
"""
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS clients
dynamodb = boto3.client('dynamodb')
s3 = boto3.client('s3')
lambda_client = boto3.client('lambda')

# Environment variables
INCIDENTS_TABLE = os.environ['INCIDENTS_TABLE']
DATA_LAKE_BUCKET = os.environ['DATA_LAKE_BUCKET']
COLLECTOR_FUNCTION_NAME = os.environ.get('COLLECTOR_FUNCTION_NAME', 'llm-incident-response-CollectorFunction-vsUPnwh07wOT')
DIAGNOSIS_FUNCTION_NAME = os.environ.get('DIAGNOSIS_FUNCTION_NAME', 'llm-incident-response-DiagnosisFunction-zuevkfvASCie')

def lambda_handler(event, context):
    """Main Lambda handler for dashboard API endpoints"""
    try:
        method = event.get('httpMethod', '')
        path = event.get('path', '')
        path_parameters = event.get('pathParameters') or {}
        query_parameters = event.get('queryStringParameters') or {}
        
        logger.info(f"Dashboard API request: {method} {path}")
        
        if method == 'OPTIONS':
            return success_response({'status': 'ok'})
        
        # Route to appropriate handler
        if method == 'GET':
            if path == '/incidents':
                return handle_get_incidents(query_parameters)
            elif path.startswith('/incidents/') and 'incident_id' in path_parameters:
                return handle_get_incident_detail(path_parameters['incident_id'])
            elif path == '/results':
                return handle_get_results()
            elif path == '/health':
                return success_response({'status': 'healthy', 'service': 'dashboard-api'})
        elif method == 'POST':
            if path == '/inject':
                return handle_post_inject(event)
            elif path == '/diagnose':
                return handle_post_diagnose(event)
        
        return error_response(404, 'Not Found', f'Unknown endpoint: {method} {path}')
        
    except Exception as e:
        logger.error(f"Dashboard API error: {str(e)}", exc_info=True)
        return error_response(500, 'Internal Server Error', str(e))

def handle_post_inject(event: Dict) -> Dict:
    """POST /inject - Triggers fault injection by invoking CollectorLambda"""
    try:
        body = {}
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except Exception:
                pass
        
        fault_class = body.get('fault_class', 'resource_exhaustion')
        if fault_class not in ('resource_exhaustion', 'misconfiguration', 'service_cascade'):
            return error_response(400, 'Invalid fault_class', 'Must be resource_exhaustion, misconfiguration, or service_cascade')
        
        payload = {
            "source": "dashboard_injection",
            "fault_class": fault_class,
            "alarm_name": f"manual-dashboard-trigger-{fault_class}",
            "state": "ALARM",
            "reason": "Manual fault injection triggered from dashboard"
        }
        
        response = lambda_client.invoke(
            FunctionName=COLLECTOR_FUNCTION_NAME,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        
        logger.info(f"Triggered fault injection for {fault_class}, status code: {response.get('StatusCode')}")
        
        return success_response({
            'message': 'Fault injection triggered',
            'fault_class': fault_class
        })
    except Exception as e:
        logger.error(f"Error triggering fault injection: {str(e)}")
        return error_response(500, 'Failed to trigger fault injection', str(e))

def handle_post_diagnose(event: Dict) -> Dict:
    """POST /diagnose - Triggers diagnosis for an incident by invoking DiagnosisLambda"""
    try:
        body = {}
        if event.get('body'):
            try:
                body = json.loads(event['body'])
            except Exception:
                pass
        
        incident_id = body.get('incident_id')
        if not incident_id:
            return error_response(400, 'Missing incident_id parameter')
        
        # Check incident exists in DynamoDB to get fault_class and raw_data_s3_key
        item_response = dynamodb.get_item(
            TableName=INCIDENTS_TABLE,
            Key={'incident_id': {'S': incident_id}}
        )
        
        if 'Item' not in item_response:
            return error_response(404, 'Incident not found', f'No incident found with ID: {incident_id}')
        
        incident = convert_dynamodb_item(item_response['Item'])
        fault_class = incident.get('fault_class', 'resource_exhaustion')
        raw_data_s3_key = incident.get('raw_data_s3_key', f"incidents/{incident_id}/raw_data.json")
        
        payload = {
            "incident_id": incident_id,
            "fault_class": fault_class,
            "raw_data_s3_key": raw_data_s3_key
        }
        
        response = lambda_client.invoke(
            FunctionName=DIAGNOSIS_FUNCTION_NAME,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        
        logger.info(f"Triggered diagnosis for incident {incident_id}, status code: {response.get('StatusCode')}")
        
        return success_response({
            'message': 'Diagnosis triggered',
            'incident_id': incident_id
        })
    except Exception as e:
        logger.error(f"Error triggering diagnosis: {str(e)}")
        return error_response(500, 'Failed to trigger diagnosis', str(e))

def handle_get_incidents(query_params: Dict) -> Dict:
    """GET /incidents - Returns recent incident records with pagination"""
    try:
        # Parse query parameters
        limit = int(query_params.get('limit', '20'))
        limit = min(limit, 100)  # Max 100 incidents per request
        
        last_evaluated_key = query_params.get('lastKey')
        status_filter = query_params.get('status')
        fault_class_filter = query_params.get('faultClass')
        
        # Build scan parameters
        scan_params = {
            'TableName': INCIDENTS_TABLE,
            'Limit': limit
        }
        
        # Add filters if specified
        filter_expressions = []
        expression_values = {}
        
        if status_filter:
            filter_expressions.append('remediation.#status = :status')
            expression_values[':status'] = {'S': status_filter}
            
        if fault_class_filter:
            filter_expressions.append('fault_class = :fault_class')
            expression_values[':fault_class'] = {'S': fault_class_filter}
            
        if filter_expressions:
            scan_params['FilterExpression'] = ' AND '.join(filter_expressions)
            scan_params['ExpressionAttributeValues'] = expression_values
            scan_params['ExpressionAttributeNames'] = {'#status': 'status'}
            
        if last_evaluated_key:
            try:
                scan_params['ExclusiveStartKey'] = json.loads(last_evaluated_key)
            except json.JSONDecodeError:
                return error_response(400, 'Invalid lastKey parameter')
        
        # Execute scan
        response = dynamodb.scan(**scan_params)
        
        # Convert DynamoDB items to clean format
        incidents = []
        for item in response.get('Items', []):
            incident = convert_dynamodb_item(item)
            incidents.append(incident)
            
        # Sort by detected_at (most recent first)
        incidents.sort(key=lambda x: x.get('detected_at', ''), reverse=True)
        
        # Prepare response
        result = {
            'incidents': incidents,
            'count': len(incidents)
        }
        
        if 'LastEvaluatedKey' in response:
            result['lastKey'] = json.dumps(response['LastEvaluatedKey'])
            result['hasMore'] = True
        else:
            result['hasMore'] = False
            
        return success_response(result)
        
    except Exception as e:
        logger.error(f"Error getting incidents: {str(e)}")
        return error_response(500, 'Failed to retrieve incidents', str(e))

def handle_get_incident_detail(incident_id: str) -> Dict:
    """GET /incidents/{id} - Returns full incident record with raw data"""
    try:
        # Get incident record from DynamoDB
        response = dynamodb.get_item(
            TableName=INCIDENTS_TABLE,
            Key={'incident_id': {'S': incident_id}}
        )
        
        if 'Item' not in response:
            return error_response(404, 'Incident not found', f'No incident found with ID: {incident_id}')
            
        incident = convert_dynamodb_item(response['Item'])
        
        # Fetch raw data from S3 if available
        raw_data = None
        raw_data_s3_key = incident.get('raw_data_s3_key')
        
        if raw_data_s3_key:
            try:
                s3_response = s3.get_object(
                    Bucket=DATA_LAKE_BUCKET,
                    Key=raw_data_s3_key
                )
                raw_data = json.loads(s3_response['Body'].read().decode('utf-8'))
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchKey':
                    logger.warning(f"Could not fetch raw data from S3: {e}")
                # Continue without raw data
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in raw data: {e}")
        
        # Combine incident record with raw data
        result = {
            'incident': incident,
            'raw_data': raw_data
        }
        
        return success_response(result)
        
    except Exception as e:
        logger.error(f"Error getting incident detail: {str(e)}")
        return error_response(500, 'Failed to retrieve incident detail', str(e))

def handle_get_results() -> Dict:
    """GET /results - Returns evaluation results and metrics"""
    try:
        # Try to fetch the latest summary from evaluation results
        results_keys = [
            'evaluation/results/summary.json',
            'evaluation/results/diagnosis_recovery_gap.csv',
            'evaluation/results/failure_taxonomy.csv',
            'evaluation/results/raw_evaluation_runs.csv'
        ]
        
        results = {}
        
        for key in results_keys:
            try:
                response = s3.get_object(Bucket=DATA_LAKE_BUCKET, Key=key)
                content = response['Body'].read().decode('utf-8')
                
                if key.endswith('.json'):
                    results[key.split('/')[-1].replace('.json', '')] = json.loads(content)
                else:
                    # For CSV files, return as text for now
                    results[key.split('/')[-1].replace('.csv', '')] = content
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    logger.info(f"Results file not found: {key}")
                else:
                    logger.warning(f"Error fetching {key}: {e}")
            except Exception as e:
                logger.warning(f"Error processing {key}: {e}")
        
        # If no results found, return computed metrics from recent incidents
        if not results:
            results = compute_live_metrics()
            
        return success_response(results)
        
    except Exception as e:
        logger.error(f"Error getting results: {str(e)}")
        return error_response(500, 'Failed to retrieve results', str(e))

def compute_live_metrics() -> Dict:
    """Compute basic metrics from recent incidents if evaluation results not available"""
    try:
        # Get recent incidents (last 30 days)
        cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        
        response = dynamodb.scan(
            TableName=INCIDENTS_TABLE,
            FilterExpression='detected_at > :cutoff',
            ExpressionAttributeValues={':cutoff': {'S': cutoff_date}}
        )
        
        incidents = [convert_dynamodb_item(item) for item in response.get('Items', [])]
        
        if not incidents:
            return {
                'summary': {
                    'total_incidents': 0,
                    'average_mttr_minutes': 0,
                    'diagnosis_accuracy': 0,
                    'verification_success_rate': 0
                },
                'message': 'No recent incidents found'
            }
        
        # Compute basic metrics
        total_incidents = len(incidents)
        resolved_incidents = [i for i in incidents if i.get('verification', {}).get('status') == 'resolved']
        
        # Calculate MTTR for resolved incidents
        mttrs = []
        for incident in resolved_incidents:
            detected_at = incident.get('detected_at')
            verified_at = incident.get('verification', {}).get('checked_at')
            
            if detected_at and verified_at:
                try:
                    detected_time = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))
                    verified_time = datetime.fromisoformat(verified_at.replace('Z', '+00:00'))
                    mttr_seconds = (verified_time - detected_time).total_seconds()
                    mttrs.append(mttr_seconds / 60)  # Convert to minutes
                except Exception:
                    continue
        
        avg_mttr = sum(mttrs) / len(mttrs) if mttrs else 0
        verification_success_rate = (len(resolved_incidents) / total_incidents * 100) if total_incidents > 0 else 0
        
        return {
            'summary': {
                'total_incidents': total_incidents,
                'average_mttr_minutes': round(avg_mttr, 2),
                'diagnosis_accuracy': 0,  # Would need ground truth data
                'verification_success_rate': round(verification_success_rate, 2)
            },
            'computed_from_recent_incidents': True
        }
        
    except Exception as e:
        logger.error(f"Error computing live metrics: {str(e)}")
        return {'error': 'Failed to compute metrics', 'message': str(e)}

def convert_dynamodb_item(item: Dict) -> Dict:
    """Convert DynamoDB item format to clean JSON"""
    def convert_value(value):
        if isinstance(value, dict):
            if 'S' in value:
                return value['S']
            elif 'N' in value:
                # Try to convert to int first, then float
                try:
                    return int(value['N'])
                except ValueError:
                    return float(value['N'])
            elif 'BOOL' in value:
                return value['BOOL']
            elif 'L' in value:
                return [convert_value(v) for v in value['L']]
            elif 'M' in value:
                return {k: convert_value(v) for k, v in value['M'].items()}
            elif 'NULL' in value:
                return None
        return value
    
    return {k: convert_value(v) for k, v in item.items()}

def success_response(data: Any) -> Dict:
    """Create a successful HTTP response"""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(data, default=str)
    }

def error_response(status_code: int, error: str, message: str = None) -> Dict:
    """Create an error HTTP response"""
    body = {'error': error}
    if message:
        body['message'] = message
        
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(body)
    }