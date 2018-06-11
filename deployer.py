#!/usr/bin/env python

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import gitlab
import os
import shutil
from io import BytesIO
import zipfile
from slugify import slugify
import re

HOST_NAME = ''
PORT_NUMBER = 8080
GITLAB_SERVER = 'https://gitlab.com'
TMP_PATH = '/tmp/deployer'
BUILD_NAME = os.environ.get('BUILD_NAME')
DEBUG = True if os.environ.get('DEBUG') == '1' else False

access_tokens = os.environ.get('GITLAB_WEBHOOK_TOKENS').split(',')
gl = gitlab.Gitlab(GITLAB_SERVER, os.environ.get('GITLAB_API_TOKEN'))

class WebhookHandler(BaseHTTPRequestHandler):
	def do_POST(self):
		if self.path == '/deployer':

			data_string = self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8')
			if DEBUG: print('Received: ', data_string)
			data = json.loads(data_string)

			if data['object_kind'] == 'build' and data['build_status'] == 'success':
				project = gl.projects.get(data['project_id'])
				build = project.jobs.get(data['build_id'])

				if not self.check_access(project):
					print('Not deployed because access token does not match.')
					return

				if not BUILD_NAME or build.name != BUILD_NAME:
					print('Not deployed because build name does not match.')
					return

				self.do_build_success(data, project, build)
			else:
				self.send_response(200)
				self.end_headers()
				self.wfile.write(b"Not interested")
				if DEBUG: print('Not deployed because it is not success build.')

	def check_access(self, project):
		if self.headers['X-Gitlab-Token'] in access_tokens:
			return True

	# Process successful build
	def do_build_success(self, data, project, build):
		# Prepare tmp dir
		if os.path.exists(TMP_PATH):
			shutil.rmtree(TMP_PATH)
		os.makedirs(TMP_PATH)

		# Download and extract archive to tmp dir
		archive = BytesIO()
		archive.write(build.artifacts())
		archive = zipfile.ZipFile(archive)
		archive.extractall(TMP_PATH)

		# Build target dir
		format_data = {
			'unsafe_received_data': data,
			'project': project,
			'build': build,
			'slug_build_ref': slugify(build.ref, to_lower=True),
			'slug_project_name': slugify(project.name, to_lower=True)
		}
		target_dir = os.environ.get('TARGET_DIR').format(**format_data)

		# Move to target dir (and remove old)

		artifact_files = list(os.scandir(TMP_PATH))
		# No files
		if (len(artifact_files) == 0):
			print('Not deployed build #{0} because in artifacts are no files.'.format(build.id))
			self.send_response(500)
			return False

		# One item and is directory
		elif (len(artifact_files) == 1 and artifact_files[0].is_dir()):
			if os.path.exists(target_dir):
				shutil.rmtree(target_dir)
			shutil.move(artifact_files[0].path, target_dir)

		# Multiple items (files or directories)
		else:
			if os.path.exists(target_dir):
				shutil.rmtree(target_dir)
			shutil.move(TMP_PATH, target_dir)

		# Respond to client
		self.send_response(200)

		print('Artifact deployed: ', target_dir)


if __name__ == '__main__':
	# Notice about removed feature
	if os.environ.get('MERGE_REQUEST_NOTE'):
		print('Feature to write note into merge request was removed, replacement is the new dynamic environments feature in GitLab, see README how to use it.')

	# Start webserver
	server_class = HTTPServer
	httpd = server_class((HOST_NAME, PORT_NUMBER), WebhookHandler)
	print("Server Starts - {}:{}".format(HOST_NAME, PORT_NUMBER))
	try:
		httpd.serve_forever()
	except KeyboardInterrupt:
		pass
	httpd.server_close()
	print("Server Stops - {}:{}".format(HOST_NAME, PORT_NUMBER))
