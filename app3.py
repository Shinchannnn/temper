from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import os
import json
import pyshark

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure secret key

# Configure upload and converted folders
UPLOAD_FOLDER = './uploads'
CONVERTED_FOLDER = './converted_json'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER

# Ensure the folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)

# MongoDB connection
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017')
db = client['template_db']  # Ensure you're using the correct database

# Change the collection name to 'templates' (instead of 'temp')
templates_collection = db['templates']

# Insert a template (for testing purposes)
template_data = {
    'template_name': 'Test Template',
    'keyValuePairs': [
        {'key': 'key1', 'value': 'value1'},
        {'key': 'key2', 'value': 'value2'}
    ],
    'createdAt': '07-01-2025'
}

# templates_collection.insert_one(template_data)





@app.route('/save_configuration', methods=['POST'])
def save_configuration():
    template_name = request.form.get('template_name')
    key = request.form.get('key')
    value = request.form.get('value')
    
    if not template_name or not key or not value:
        flash('Template name and key-value pairs are required!', 'error')
        return redirect(url_for('validate'))
    
    template = templates_collection.find_one({"templateName": template_name})
    if template and template.get('locked', False):
        flash('Configuration is locked and cannot be modified.', 'error')
        return redirect(url_for('validate'))
    
    templates_collection.update_one(
        {"templateName": template_name},
        {"$set": {f"keyValues.{key}": value}},
        upsert=True
    )
    
    flash('Configuration saved successfully!', 'success')
    return redirect(url_for('template_structure'))
@app.route('/')
def upload_form():
    return render_template('upload.html')

# 
@app.route('/', methods=['POST'])
def upload_file():
    username = request.form['username']
    file = request.files['file']

    if file and file.filename.endswith('.pcap'):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Convert PCAP to JSON
        json_filename = f"{username}_{file.filename.replace('.pcap', '.json')}"
        json_filepath = os.path.join(app.config['CONVERTED_FOLDER'], json_filename)

        try:
            # Convert file synchronously on the main thread
            convert_pcap_to_json(file_path, json_filepath)
            flash('File uploaded and converted successfully', 'success')
        except Exception as e:
            flash(f'Error during conversion: {e}', 'error')
            return redirect(url_for('upload_form'))

        session['success_message'] = 'File uploaded and converted successfully'
        session['selected_file'] = json_filename
        
        # Redirect directly to search_results with the converted file
        return redirect(url_for('search_results', filename=json_filename))

    flash('Invalid file type, only .pcap files are allowed', 'error')
    return redirect(url_for('upload_form'))

# Modify the search_results route to use the filename directly from the URL
@app.route('/search_results/<filename>')
def search_results(filename):
    file_path = os.path.join(app.config['CONVERTED_FOLDER'], filename)

    if not os.path.exists(file_path):
        flash('File not found!', 'error')
        return redirect(url_for('upload_form'))  # Redirect back to upload if file doesn't exist

    with open(file_path) as f:
        file_data = json.load(f)

    # Retrieve template_name from session or set a default
    template_name = session.get('template_name', f"Template_{filename}")
    session['template_name'] = template_name

    return render_template('search_results.html', filename=filename, json_data=file_data, template_name=template_name)


# @app.route('/view_files', methods=['GET', 'POST'])
# def view_files():
#     converted_files = [
#         file for file in os.listdir(app.config['CONVERTED_FOLDER']) if file.endswith('.json')
#     ]

#     if request.method == 'POST':
#         selected_file = request.form.get('selected_file')
#         session['selected_file'] = selected_file
#         return redirect(url_for('search_results', filename=selected_file))

#     return render_template('view_files.html', files=converted_files)

# @app.route('/search_results/<filename>')
# def search_results(filename):
#     file_path = os.path.join(app.config['CONVERTED_FOLDER'], filename)

#     if not os.path.exists(file_path):
#         flash('File not found!', 'error')
#         return redirect(url_for('view_files'))

#     with open(file_path) as f:
#         file_data = json.load(f)

#     # Retrieve template_name from session or set a default
#     template_name = session.get('template_name', f"Template_{filename}")
#     session['template_name'] = template_name

#     return render_template('search_results.html', filename=filename, json_data=file_data, template_name=template_name)



@app.route('/api/search_keys', methods=['GET'])
def search_keys():
    query = request.args.get('q', '').lower()
    filename = session.get('selected_file')
    file_path = os.path.join(app.config['CONVERTED_FOLDER'], filename)


    if not os.path.exists(file_path):
        return jsonify([])

    with open(file_path) as f:
        file_data = json.load(f)

    suggestions = search_json(file_data, query)
    return jsonify(suggestions)

@app.route('/api/search_suggestions', methods=['GET'])
def search_suggestions():
    query = request.args.get('q', '').lower()
    files = [file for file in os.listdir(app.config['CONVERTED_FOLDER']) if file.endswith('.json')]

    suggestions = []
    for file in files:
        if query in file.lower():
            suggestions.append({"filename": file})

    return jsonify(suggestions)

def search_json(data, query):
    matches = []
    if isinstance(data, dict):
        for key, value in data.items():
            if query in key.lower():
                matches.append({"key": key, "value": value})
            if isinstance(value, (dict, list)):
                matches.extend(search_json(value, query))
    elif isinstance(data, list):
        for item in data:
            matches.extend(search_json(item, query))
    return matches

def convert_pcap_to_json(input_pcap_path, output_json_path):
    """Convert a PCAP file to a JSON file using PyShark."""
    packets = pyshark.FileCapture(input_pcap_path)
    data = []

    # Extract packet details
    for packet in packets:
        packet_dict = {}
        for layer in packet.layers:
            packet_dict[layer.layer_name] = layer._all_fields
        data.append(packet_dict)

    with open(output_json_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)

    packets.close()

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.before_request
def initialize_session():
    if 'validated_pairs' not in session:
        session['validated_pairs'] = []
    else:
        try:
            session['validated_pairs'] = json.loads(json.dumps(session['validated_pairs']))
        except json.JSONDecodeError:
            session['validated_pairs'] = []

@app.route('/validate', methods=['GET'])
def validate():
    key = request.args.get('key')
    value = request.args.get('value')
    session['validated_pairs'] = session.get('validated_pairs', []) + [{'key': key, 'value': value}]
    app.logger.debug(f"Validated pairs: {session['validated_pairs']}")
    return render_template('Validate.html', key=key, value=value)






   
@app.route('/delete-template', methods=['DELETE'])
def delete_template():
    try:
        data = request.json
        template_name = data.get("templateName")

        if not template_name:
            return jsonify({"error": "Template name is required"}), 400

        delete_result = templates_collection.delete_one({"templateName": template_name})

        if delete_result.deleted_count == 0:
            return jsonify({"error": "Template not found"}), 404

        return jsonify({"message": "Template deleted successfully!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/templates', methods=['GET'])
def get_templates():
    return jsonify(templates)


  # Store in session
        # Existing code...
# @app.route('/save_test', methods=['GET', 'POST'])
# def save_test():
#     if request.method == 'POST':
#         template_data = {'name': 'Test Template', 'data': [{'key': 'testKey', 'value': 'testValue'}]}
#         template_path = './templates_storage/Test_Template.json'
#         try:
#             with open(template_path, 'w') as f:
#                 json.dump(template_data, f, indent=4)
#             flash('Test template saved successfully!', 'success')
#         except Exception as e:
#             flash(f'Error saving test template: {e}', 'error')
#         return redirect(url_for('template_structure'))
    
#     return render_template('template_structure.html')


#   @app.route('/save_test', methods=['GET', 'POST'])
# def save_test():
#     print("Save Test Route Triggered")  # Debug line to confirm route is accessed
#     if request.method == 'POST':
#         template_data = {'name': 'Test Template', 'data': [{'key': 'testKey', 'value': 'testValue'}]}
        
#         # Full absolute path
#         template_path = os.path.abspath('./templates_storage/Test_Template.json')
#         print(f"Saving template at: {template_path}")
        
#         try:
#             with open(template_path, 'w') as f:
#                 json.dump(template_data, f, indent=4)
#             flash('Test template saved successfully!', 'success')
#         except Exception as e:
#             flash(f'Error saving test template: {e}', 'error')
        
#         return redirect(url_for('template_structure'))
    
#     return render_template('template_structure.html')



    # Existing code...
@app.route('/delete-key-value', methods=['DELETE'])
def delete_key_value():
    try:
        data = request.json
        template_name = data.get("templateName")
        key = data.get("key")

        if not template_name or not key:
            return jsonify({"error": "Template Name and Key are required"}), 400

        # Use MongoDB $unset to remove the key from the 'keyValues' object
        result = templates_collection.update_one(
            {"templateName": template_name},
            {"$unset": {f"keyValues.{key}": ""}}  # Remove the key from 'keyValues'
        )

        if result.modified_count > 0:
            return jsonify({"message": "Key-Value deleted successfully!"}), 200
        else:
            return jsonify({"error": "Key-Value not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/update-template-values', methods=['POST'])
def update_template_values():
    try:
        data = request.json
        template_name = data.get("templateName")
        updated_values = data.get("updatedValues")

        if not template_name or not updated_values:
            return jsonify({"error": "Template name and updated values are required"}), 400

        template = templates_collection.find_one({"templateName": template_name})
        if not template:
            return jsonify({"error": "Template not found"}), 404

        # Prepare updates only for existing fields
        update_fields = {}
        for key, value in updated_values.items():
            if key in template:  # Only update existing fields
                update_fields[key] = value
            else:
                print(f"Skipping non-existing field: {key}")  # Debugging

        print("Updating fields:", update_fields)  # Debugging

        update_result = templates_collection.update_one(
            {"templateName": template_name},
            {"$set": update_fields}
        )

        if update_result.modified_count == 0:
            return jsonify({"error": "No matching fields found to update"}), 404

        return jsonify({"message": "Updated successfully!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/api/save_template', methods=['POST'])
def save_template():
    try:
        data = request.json
        template_name = data.get('templateName')
        key_value_pairs = data.get('keyValuePairs')

        if not template_name or not key_value_pairs:
            return jsonify({"error": "Template name and key-value pairs are required"}), 400

        formatted_data = {pair['key']: pair['value'] for pair in key_value_pairs}

        existing_template = templates_collection.find_one({"templateName": template_name})

        if existing_template:
            templates_collection.update_one(
                {"templateName": template_name},
                {"$set": formatted_data}
            )
        else:
            templates_collection.insert_one({
                "templateName": template_name,
                **formatted_data
            })

        return jsonify({"message": "Template saved successfully", "redirect": url_for('template_structure')}), 201

    except Exception as e:
        print("Error in /api/save_template:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route('/get-validated-pairs', methods=['GET'])
def get_validated_pairs():
    try:
        template_name = request.args.get('templateName')
        if not template_name:
            return jsonify({"error": "Template name is required"}), 400

        template = templates_collection.find_one({"templateName": template_name}, {"_id": 0})
        if not template:
            return jsonify({"error": "Template not found"}), 404

        template_data = {key: value for key, value in template.items() if key != "templateName"}
        return jsonify({"templateName": template_name, "keyValuePairs": template_data})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------- Delete Key-Value Pair from MongoDB ----------------------




@app.route('/api/get_templates', methods=['GET'])
def get_all_templates():
    try:
        templates = list(templates_collection.find({}, {"_id": 0, "templateName": 1}))
        return jsonify(templates)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/api/get_template', methods=['GET'])
def get_template():
    try:
        template_name = request.args.get('name')
        if not template_name:
            return jsonify({"error": "Template name is required"}), 400

        template = templates_collection.find_one({"templateName": template_name}, {"_id": 0})
        if not template:
            return jsonify({"error": "Template not found"}), 404

        # Remove templateName from the response
        del template["templateName"]

        return jsonify(template), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/get-latest-template', methods=['GET'])
def get_latest_template():
    try:
        latest_template = templates_collection.find_one({}, {"_id": 0}, sort=[("_id", -1)])

        if not latest_template:
            return jsonify({"error": "No template found"}), 404

        return jsonify({
            "templateName": latest_template["templateName"],
            "keyValuePairs": {k: v for k, v in latest_template.items() if k != "templateName"}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/save-key-value', methods=['POST'])
def save_key_value():
    try:
        data = request.json
        template_name = data.get("templateName")
        key = data.get("key")
        value = data.get("value")

        if not template_name or not key or not value:
            return jsonify({"error": "Template Name, Key, and Value are required"}), 400

        # Check if the template exists
        existing_template = templates_collection.find_one({"templateName": template_name})

        if existing_template:
            # Update the existing template with new key-value
            templates_collection.update_one(
                {"templateName": template_name},
                {"$set": {key: value}}
            )
        else:
            # Insert a new template with the key-value pair
            templates_collection.insert_one({
                "templateName": template_name,
                key: value
            })

        return jsonify({"message": "Key-Value stored successfully!"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/lock-template', methods=['POST'])
def lock_template():
    data = request.json
    template_name = data.get("templateName")
    
    if not template_name:
        return jsonify({"error": "Template name is required"}), 400
    
    templates_collection.update_one(
        {"templateName": template_name},
        {"$set": {"locked": True}}
    )
    
    return jsonify({"message": "Template locked successfully."}), 200

@app.route('/template_structure', methods=['GET'])
def template_structure():
    templates = list(templates_collection.find({}, {"_id": 0}))
    return render_template('template_structure.html', templates=templates)
@app.route('/pcapparser')
def pcap_parser_page():
    return render_template('pcapparser.html')  



@app.route('/api/get_template_details', methods=['GET'])
def get_template_details():
    try:
        template_name = request.args.get('name')
        if not template_name:
            return jsonify({"error": "Template name is required"}), 400

        template = templates_collection.find_one({"templateName": template_name}, {"_id": 0})
        if not template:
            return jsonify({"error": "Template not found"}), 404

        del template["templateName"]

        return jsonify(template), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/analyze', methods=['GET'])
def analyze():
    try:
        template_name = request.args.get('templateName')
        filename = request.args.get('filename')

        if not template_name or not filename:
            return jsonify({"error": "Template name and filename are required"}), 400

        template = templates_collection.find_one({"templateName": template_name}, {"_id": 0})
        if not template:
            return jsonify({"error": "Template not found"}), 404

        file_path = os.path.join(app.config['CONVERTED_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404

        with open(file_path) as f:
            file_data = json.load(f)

        matched_key_values = {}
        for key, value in template.items():
            if key in file_data:
                matched_key_values[key] = file_data[key]

        return jsonify(matched_key_values), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/replace-template-values', methods=['POST'])
def replace_template_values():
    try:
        data = request.json
        template_name = data.get("templateName")
        updated_values = data.get("updatedValues")

        if not template_name or not updated_values:
            return jsonify({"error": "Template name and updated values are required"}), 400

        # Delete the old template
        templates_collection.delete_one({"templateName": template_name})

        # Insert the new template with updated values
        templates_collection.insert_one({
            "templateName": template_name,
            "keyValues": updated_values  # Store key-value pairs directly under 'keyValues'
        })

        return jsonify({"message": "Template updated successfully!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload-pcap', methods=['POST'])
def upload_pcap():
    if 'pcapFile' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['pcapFile']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and file.filename.endswith('.pcap'):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Convert PCAP to JSON
        json_filename = file.filename.replace('.pcap', '.json')
        json_filepath = os.path.join(app.config['CONVERTED_FOLDER'], json_filename)

        try:
            convert_pcap_to_json(file_path, json_filepath)
            session['uploaded_file'] = json_filename
            return jsonify({"message": "File uploaded and converted successfully", "filename": json_filename}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Invalid file type, only .pcap files are allowed"}), 400

# Route to handle analysis
@app.route('/analyze-pcap', methods=['POST'])
def analyze_pcap():
    try:
        template_name = request.json.get('templateName')
        filename = session.get('uploaded_file')

        if not template_name or not filename:
            return jsonify({"error": "Template name and filename are required"}), 400

        template = templates_collection.find_one({"templateName": template_name}, {"_id": 0})
        if not template:
            return jsonify({"error": "Template not found"}), 404

        file_path = os.path.join(app.config['CONVERTED_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404

        with open(file_path) as f:
            file_data = json.load(f)

        matched_key_values = {}
        for key, value in template.items():
            if key in file_data:
                matched_key_values[key] = file_data[key]

        # Calculate match percentage
        total_keys = len(template)
        matched_keys = len(matched_key_values)
        match_percentage = (matched_keys / total_keys) * 100

        session['analysis_result'] = {
            "templateName": template_name,
            "providedKeyValues": template,
            "matchedKeyValues": matched_key_values,
            "matchPercentage": match_percentage
        }

        return jsonify({"message": "Analysis completed", "matchPercentage": match_percentage}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to get analysis results
@app.route('/get-analysis-result', methods=['GET'])
def get_analysis_result():
    result = session.get('analysis_result')
    if not result:
        return jsonify({"error": "No analysis result found"}), 404

    return jsonify(result), 200

# Function to convert PCAP to JSON
def convert_pcap_to_json(input_pcap_path, output_json_path):
    """Convert a PCAP file to a JSON file using PyShark."""
    packets = pyshark.FileCapture(input_pcap_path)
    data = []

    # Extract packet details
    for packet in packets:
        packet_dict = {}
        for layer in packet.layers:
            packet_dict[layer.layer_name] = layer._all_fields
        data.append(packet_dict)

    with open(output_json_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)

    packets.close()

if __name__ == '__main__':
    app.run(debug=True, )
