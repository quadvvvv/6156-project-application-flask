import io
import json
import uuid

from google.api_core.exceptions import NotFound
from google.cloud.pubsub import PublisherClient
# from google.pubsub_v1.types import Encoding
from google.cloud import pubsub_v1

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
# from avro import schema, io
import os 

# App Engine App: This refers to the specific instance of your application hosted on Google App Engine. 
# It includes configuration settings, deployment details, and the runtime environment.

# Project: In GCP, a project is a container for resources such as App Engine apps, 
# Cloud Storage, Compute Engine instances, and more. It defines the namespace for your 
# resources and provides a way to manage and organize them.

# note: direct connections to external databases, like an AWS RDS instance, are not allowed due to security and networking restrictions

app = Flask(__name__)

# Event publishing related setup
project_id = 'application-microservice'
topic_name = 'status-update-result'

# Create a Pub/Sub publisher client
publisher = pubsub_v1.PublisherClient()

# Define the topic path
topic_path = publisher.topic_path(project_id, topic_name)

# Database related setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://desperado:6156dbdesperado@desperado-db.ctldmj6kaxoc.us-east-2.rds.amazonaws.com:5432/application'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Application(db.Model):
    applicationid = db.Column(db.String(32), primary_key=True)
    jobid = db.Column(db.String(255))
    applicantname = db.Column(db.String(255))
    applicantemail = db.Column(db.String(255))
    recruitername = db.Column(db.String(255))
    recruiteremail = db.Column(db.String(255))
    status = db.Column(db.String(255))

app.app_context().push()

# Create tables
db.create_all()

@app.route('/', methods=['GET'])
def get_dummy():
    return jsonify({"message": f"Helloworld"}), 200

@app.route('/application/', methods=['GET'])
def get_all_applications():
    applications = Application.query.all()
    result = [{"applicationid": app.applicationid, "jobid": app.jobid, "applicantname": app.applicantname, "applicantemail": app.applicantemail, "recruitername": app.recruitername, "status": app.status} for app in applications]
    return jsonify(result)


@app.route('/application/<application_id>', methods=['GET'])
def get_application(application_id):
    application = Application.query.get(application_id)
    if application:
        return jsonify({"applicationid": application.applicationid, "jobid": application.jobid, "applicantname": application.applicantname, "applicantemail": application.applicantemail, "recruitername": application.recruitername, "recruiteremail": application.recruiteremail, "status": application.status})
    else:
        return jsonify({"error": "Application not found"}), 404

@app.route('/application/total_count', methods=['GET'])
def get_total_count():
    try:
        # Execute a query to get the total count
        total_count = db.session.query(Application).count()

        # Return the total count as a JSON response
        return jsonify({"total_count": total_count})

    except Exception as e:
        # Handle exceptions, log errors, etc.
        return jsonify({"error": str(e)}), 500

@app.route('/application/recruiters/<recruiterEmail>', methods=['GET'])
def get_recruiter_applications(recruiterEmail):
    recruiter_applications = Application.query.filter_by(recruiteremail=recruiterEmail).all()
    result = [{"applicationid": app.applicationid, "jobid": app.jobid, "applicantname": app.applicantname, "applicantemail": app.applicantemail, "recruitername": app.recruitername, "status": app.status} for app in recruiter_applications]
    return jsonify(result)

@app.route('/application/jobseekers/<jobseekerEmail>', methods=['GET'])
def get_jobseeker_applications(jobseekerEmail):
    jobseeker_applications = Application.query.filter_by(applicantemail=jobseekerEmail).all()
    result = [{"applicationid": app.applicationid, "jobid": app.jobid, "applicantname": app.applicantname, "applicantemail": app.applicantemail, "recruitername": app.recruitername, "status": app.status} for app in jobseeker_applications]
    return jsonify(result)

@app.route('/application', methods=['POST'])
def create_application():
    data = request.json
    new_uuid = uuid.uuid4()
    uuid_without_hyphens = str(new_uuid).replace("-", "")
    new_application = Application(
        applicationid= (uuid_without_hyphens),
        jobid=data.get('jobid'),
        applicantname=data.get('applicantname'),
        applicantemail=data.get('applicantemail'),
        recruitername=data.get('recruitername'),
        recruiteremail=data.get('recruiteremail'),
        status='Pending'
    )
    db.session.add(new_application)
    db.session.commit()
    return jsonify({"message": "Application created successfully", "application": {"applicationid": new_application.applicationid, "jobid": new_application.jobid, "applicantname": new_application.applicantname, "applicantemail": new_application.applicantemail, "recruitername": new_application.recruitername, "status": new_application.status}}), 201

@app.route('/application/<application_id>/status', methods=['PUT'])
def update_application_status(application_id):
    application = Application.query.get(application_id)
    if application:
        data = request.json
        new_status = data.get('status')
        if new_status:
            # Updat the status in the database
            application.status = new_status
            db.session.commit()

            # Publish an event to the Pub/Sub topic
            message_data = {
                'application_id': application_id,
                'applicant_email': application.applicantemail,
                'new_status': new_status
            }
            message_data = json.dumps(message_data)
            data = message_data.encode("utf-8")
            future = publisher.publish(topic_path, data)

            # Wait for the message to be published
            future.result()

            return jsonify({"message": f"Application status updated to {new_status}"}), 200
        else:
            return jsonify({"error": "Missing 'status' field in the request body"}), 400
    else:
        return jsonify({"error": "Application not found"}), 404

@app.route('/application/<application_id>', methods=['DELETE'])
def withdraw_application(application_id):
    application = Application.query.get(application_id)
    if application:
        db.session.delete(application)
        db.session.commit()
        return jsonify({"message": "Application withdrawn successfully"}), 200
    else:
        return jsonify({"error": "Application not found"}), 404


if __name__ == '__main__':
    # Use os.environ.get('PORT', 5000) to dynamically get the port
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
