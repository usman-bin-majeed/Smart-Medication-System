from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from models import db_manager
from datetime import datetime
import os
from bson import ObjectId

app = Flask(__name__)
app.secret_key = "USMAN313"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            role = request.form.get('role')
            name = request.form.get('name')

            # Validate required fields
            if not all([email, password, role, name]):
                return jsonify({'error': 'All fields are required'}), 400

            # Create user account
            result = db_manager.create_user(email, password, role, name=name)
            if 'error' in result:
                return jsonify({'error': result['error']}), 400

            user_id = result['user_id']

            # Create role-specific profile
            if role == 'patient':
                age = request.form.get('age')
                gender = request.form.get('gender')
                allergies = request.form.get('allergies', '')
                conditions = request.form.get('conditions', '')
                
                # Only create profile if additional info is provided
                if age and gender:
                    allergies_list = [a.strip() for a in allergies.split(',') if a.strip()] if allergies else []
                    conditions_list = [c.strip() for c in conditions.split(',') if c.strip()] if conditions else []
                    
                    profile_result = db_manager.create_patient_profile(
                        user_id=user_id,
                        name=name,
                        age=int(age),
                        gender=gender,
                        allergies=allergies_list,
                        conditions=conditions_list
                    )
                    
                    if 'error' in profile_result:
                        return jsonify({'error': 'Failed to create patient profile'}), 500

            elif role == 'guardian':
                phone = request.form.get('phone', '')
                relationship = request.form.get('relationship', '')
                
                if phone and relationship:
                    profile_result = db_manager.create_guardian_profile(
                        user_id=user_id,
                        name=name,
                        phone=phone,
                        relationship=relationship
                    )
                    
                    if 'error' in profile_result:
                        return jsonify({'error': 'Failed to create guardian profile'}), 500

            elif role == 'pharmacy':
                address = request.form.get('address', '')
                phone = request.form.get('phone', '')
                license_number = request.form.get('license_number', '')
                
                if address and phone and license_number:
                    # Note: create_pharmacy creates both user and pharmacy profile
                    # Since we already created the user, we need to create only pharmacy profile
                    pharmacy_data = {
                        "user_id": ObjectId(user_id),
                        "name": name,
                        "address": address,
                        "phone": phone,
                        "license_number": license_number,
                        "is_verified": False,
                        "delivery_available": False,
                        "inventory": [],
                        "created_at": datetime.utcnow()
                    }
                    
                    db_manager.pharmacies.insert_one(pharmacy_data)

            return jsonify({'success': True, 'message': 'Registration successful', 'redirect': url_for('login')})

        except Exception as e:
            return jsonify({'error': f'Registration failed: {str(e)}'}), 500

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            
            if not email or not password:
                return jsonify({'error': 'Email and password are required'}), 400
            
            user = db_manager.authenticate_user(email, password)
            if user:
                session['user_id'] = user['user_id']
                session['role'] = user['role']
                session['email'] = user['email']
                
                return jsonify({
                    'success': True, 
                    'message': 'Login successful',
                    'redirect': url_for('dashboard')
                })
            else:
                return jsonify({'error': 'Invalid email or password'}), 401
                
        except Exception as e:
            return jsonify({'error': f'Login failed: {str(e)}'}), 500
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_role = session['role']
    user_id = session['user_id']

    try:
        if user_role == 'patient':
            patient = db_manager.get_patient_by_user_id(user_id)
            if not patient:
                flash('Please complete your profile setup', 'warning')
                return redirect(url_for('setup_profile'))

            today_meds = db_manager.get_today_medications(str(patient['_id']))
            compliance = db_manager.get_medication_compliance(str(patient['_id']))

            # Find next medication
            next_med = None
            current_time = datetime.now().strftime('%H:%M')
            for med in today_meds:
                if not med['taken'] and med['time'] >= current_time:
                    next_med = med
                    break

            return render_template('patient_dashboard.html',
                                   patient=patient,
                                   today_meds=today_meds,
                                   compliance=compliance,
                                   next_med=next_med)
                                   
        elif user_role == 'guardian':
            guardian = db_manager.guardians.find_one({"user_id": ObjectId(user_id)})
            if not guardian:
                flash('Please complete your profile setup', 'warning')
                return redirect(url_for('setup_profile'))
            return render_template('guardian_dashboard.html', guardian=guardian)
            
        elif user_role == 'pharmacy':
            pharmacy = db_manager.pharmacies.find_one({"user_id": ObjectId(user_id)})
            if not pharmacy:
                flash('Please complete your profile setup', 'warning')
                return redirect(url_for('setup_profile'))
            return render_template('pharmacy_dashboard.html', pharmacy=pharmacy)

    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('login'))

    return render_template('dashboard.html')

@app.route('/setup_profile', methods=['GET', 'POST'])
def setup_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            user_id = session['user_id']
            role = session['role']
            
            if role == 'patient':
                name = request.form.get('name')
                age = request.form.get('age')
                gender = request.form.get('gender')
                allergies = request.form.get('allergies', '')
                conditions = request.form.get('conditions', '')
                
                if not all([name, age, gender]):
                    return jsonify({'error': 'Name, age, and gender are required'}), 400
                
                allergies_list = [a.strip() for a in allergies.split(',') if a.strip()] if allergies else []
                conditions_list = [c.strip() for c in conditions.split(',') if c.strip()] if conditions else []
                
                result = db_manager.create_patient_profile(
                    user_id=user_id,
                    name=name,
                    age=int(age),
                    gender=gender,
                    allergies=allergies_list,
                    conditions=conditions_list
                )
                
                if 'patient_id' in result:
                    return jsonify({'success': True, 'redirect': url_for('dashboard')})
                else:
                    return jsonify({'error': 'Failed to create profile'}), 500
                    
            elif role == 'guardian':
                name = request.form.get('name')
                phone = request.form.get('phone')
                relationship = request.form.get('relationship')
                
                if not all([name, phone, relationship]):
                    return jsonify({'error': 'All fields are required'}), 400
                
                result = db_manager.create_guardian_profile(
                    user_id=user_id,
                    name=name,
                    phone=phone,
                    relationship=relationship
                )
                
                if 'guardian_id' in result:
                    return jsonify({'success': True, 'redirect': url_for('dashboard')})
                else:
                    return jsonify({'error': 'Failed to create profile'}), 500
                    
        except Exception as e:
            return jsonify({'error': f'Profile setup failed: {str(e)}'}), 500
    
    return render_template('setup_profile.html', role=session.get('role'))

@app.route('/medications')
def medications():
    if 'user_id' not in session or session['role'] != 'patient':
        return redirect(url_for('login'))

    try:
        patient = db_manager.get_patient_by_user_id(session['user_id'])
        if not patient:
            return redirect(url_for('setup_profile'))

        medications = db_manager.get_patient_medications(str(patient['_id']))
        # Convert ObjectId to string for each medication 
        for med in medications:
            med['_id'] = str(med['_id'])
            med['patient_id'] = str(med['patient_id'])
            
        
        return render_template('medications.html', medications=medications)
    except Exception as e:
        flash(f'Error loading medications: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/api/medications')
def api_medications():
    if 'user_id' not in session or session['role'] != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        patient = db_manager.get_patient_by_user_id(session['user_id'])
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        meds = db_manager.get_patient_medications(str(patient['_id']))
        # Convert ObjectId to string for JSON serialization
        for med in meds:
            med['_id'] = str(med['_id'])
            med['patient_id'] = str(med['patient_id'])
        
        return jsonify(meds)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# @app.route('/add_medication', methods=['GET', 'POST'])
# def add_medication():
#     if 'user_id' not in session or session['role'] != 'patient':
#         return redirect(url_for('login'))

#     if request.method == 'POST':
#         try:
#             patient = db_manager.get_patient_by_user_id(session['user_id'])
#             if not patient:
#                 return jsonify({'error': 'Patient profile not found'}), 404

#             # Handle both form data and JSON data
#             if request.is_json:
#                 data = request.get_json()
#             else:
#                 data = request.form.to_dict()
#                 # Handle times as form data (comma-separated string)
#                 if 'times' in data and isinstance(data['times'], str):
#                     data['times'] = [t.strip() for t in data['times'].split(',') if t.strip()]

#             if not data:
#                 return jsonify({'error': 'No data provided'}), 400

#             med_name = data.get('medication_name', '').strip()
#             dosage = data.get('dosage', '').strip()
#             frequency = data.get('frequency', '').strip()
#             times = data.get('times', [])
#             notes = data.get('notes', '').strip()

#             # Validation
#             if not all([med_name, dosage, frequency]):
#                 return jsonify({'error': 'Medication name, dosage, and frequency are required'}), 400

#             if not times or not isinstance(times, list):
#                 return jsonify({'error': 'At least one time must be specified'}), 400

#             # Validate time format
#             for time_str in times:
#                 try:
#                     datetime.strptime(time_str, '%H:%M')
#                 except ValueError:
#                     return jsonify({'error': f'Invalid time format: {time_str}. Use HH:MM format'}), 400

#             result = db_manager.add_medication(
#                 patient_id=str(patient['_id']),
#                 med_name=med_name,
#                 dosage=dosage,
#                 frequency=frequency,
#                 times=times,
#                 notes=notes
#             )

#             if 'medication_id' in result:
#                 return jsonify({'success': True, 'message': 'Medication added successfully'})
#             else:
#                 return jsonify({'error': 'Failed to add medication'}), 500

#         except Exception as e:
#             return jsonify({'error': f'Error adding medication: {str(e)}'}), 500

#     return render_template('add_medication.html')

#----------Hadi--------
@app.route('/add_medication', methods=['GET', 'POST'])
def add_medication():
    if 'user_id' not in session or session['role'] != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401

    if request.method == 'POST':
        try:
            patient = db_manager.get_patient_by_user_id(session['user_id'])
            if not patient:
                return jsonify({'error': 'Patient profile not found'}), 404

            data = request.get_json()
            
            # Validate required fields
            if not all([data.get('medication_name'), data.get('dosage'), data.get('frequency')]):
                return jsonify({'error': 'Required fields missing'}), 400

            result = db_manager.add_medication(
                patient_id=str(patient['_id']),
                med_name=data['medication_name'],
                dosage=data['dosage'],
                frequency=data['frequency'],
                times=data['times'],
                notes=data.get('notes', ''),
                side_effects=data.get('side_effects', ''),
                storage=data.get('storage', ''),
                refill_date=data.get('refill_date')
            )

            if 'medication_id' in result:
                return jsonify({
                    'success': True, 
                    'message': 'Medication added successfully',
                    'medication_id': result['medication_id']
                })
            else:
                return jsonify({'error': result.get('error', 'Failed to add medication')}), 500

        except Exception as e:
            return jsonify({'error': f'Error adding medication: {str(e)}'}), 500

    return render_template('add_medication.html')

@app.route('/api/medications/<medication_id>', methods=['PUT'])
def update_medication(medication_id):
    if 'user_id' not in session or session['role'] != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        patient = db_manager.get_patient_by_user_id(session['user_id'])
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        data = request.get_json()
        
        # Validate required fields
        if not all([data.get('medication_name'), data.get('dosage'), data.get('frequency')]):
            return jsonify({'error': 'Required fields missing'}), 400

        # Verify medication belongs to patient
        medication = db_manager.medications.find_one({
            "_id": ObjectId(medication_id),
            "patient_id": patient['_id']
        })
        
        if not medication:
            return jsonify({'error': 'Medication not found'}), 404

        result = db_manager.update_medication(
            medication_id=medication_id,
            med_name=data['medication_name'],
            dosage=data['dosage'],
            frequency=data['frequency'],
            times=data['times'],
            notes=data.get('notes', ''),
            side_effects=data.get('side_effects', ''),
            storage=data.get('storage', ''),
            refill_date=data.get('refill_date')
        )

        if result.get('success'):
            return jsonify({'success': True, 'message': 'Medication updated successfully'})
        else:
            return jsonify({'error': result.get('error', 'Failed to update medication')}), 500

    except Exception as e:
        return jsonify({'error': f'Error updating medication: {str(e)}'}), 500

@app.route('/api/medications/<medication_id>', methods=['DELETE'])
def delete_medication(medication_id):
    if 'user_id' not in session or session['role'] != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        patient = db_manager.get_patient_by_user_id(session['user_id'])
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        # Verify medication belongs to patient
        medication = db_manager.medications.find_one({
            "_id": ObjectId(medication_id),
            "patient_id": patient['_id']
        })
        
        if not medication:
            return jsonify({'error': 'Medication not found'}), 404

        result = db_manager.delete_medication(medication_id)
        
        if result.get('success'):
            return jsonify({'success': True, 'message': 'Medication deleted successfully'})
        else:
            return jsonify({'error': result.get('error', 'Failed to delete medication')}), 500

    except Exception as e:
        return jsonify({'error': f'Error deleting medication: {str(e)}'}), 500
    
@app.route('/api/medications/<medication_id>', methods=['GET'])
def get_medication(medication_id):
    if 'user_id' not in session or session['role'] != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        patient = db_manager.get_patient_by_user_id(session['user_id'])
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        # Convert string ID to ObjectId
        med_id = ObjectId(medication_id)
        
        medication = db_manager.medications.find_one({
            "_id": med_id,
            "patient_id": patient['_id']
        })
        
        if not medication:
            return jsonify({'error': 'Medication not found'}), 404
            
        # Convert ObjectIds to strings for JSON serialization
        medication['_id'] = str(medication['_id'])
        medication['patient_id'] = str(medication['patient_id'])
        
        # Convert datetime objects to string format
        if medication.get('refill_date'):
            medication['refill_date'] = medication['refill_date'].strftime('%Y-%m-%d')
        
        return jsonify(medication)
            
    except Exception as e:
        return jsonify({'error': f'Error loading medication: {str(e)}'}), 500


@app.route('/take_medication', methods=['POST'])
def take_medication():
    if 'user_id' not in session or session['role'] != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        if not data or 'medication_id' not in data:
            return jsonify({'error': 'Medication ID is required'}), 400

        medication_id = data['medication_id']
        patient = db_manager.get_patient_by_user_id(session['user_id'])
        if not patient:
            return jsonify({'error': 'Patient profile not found'}), 404

        # Verify medication belongs to patient
        medication = db_manager.medications.find_one({
            "_id": ObjectId(medication_id),
            "patient_id": patient['_id']
        })
        
        if not medication:
            return jsonify({'error': 'Medication not found'}), 404

        result = db_manager.log_medication_taken(
            patient_id=str(patient['_id']),
            medication_id=medication_id
        )
        
        if 'log_id' in result:
            return jsonify({'success': True, 'message': 'Medication marked as taken'})
        else:
            return jsonify({'error': 'Failed to log medication'}), 500

    except Exception as e:
        return jsonify({'error': f'Error logging medication: {str(e)}'}), 500

@app.route('/symptoms')
def symptoms():
    if 'user_id' not in session or session['role'] != 'patient':
        return redirect(url_for('login'))
    return render_template('symptoms.html')

@app.route('/log_symptoms', methods=['POST'])
def log_symptoms():
    if 'user_id' not in session or session['role'] != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        patient = db_manager.get_patient_by_user_id(session['user_id'])
        if not patient:
            return jsonify({'error': 'Patient profile not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        mood = int(data.get('mood', 0))
        energy_level = int(data.get('energy_level', 0))
        pain_level = int(data.get('pain_level', 0))
        side_effects = data.get('side_effects', [])
        notes = data.get('notes', '')

        # Validate scale values
        if not all(1 <= val <= 10 for val in [mood, energy_level, pain_level]):
            return jsonify({'error': 'Scale values must be between 1 and 10'}), 400

        result = db_manager.log_symptom(
            patient_id=str(patient['_id']),
            mood=mood,
            energy_level=energy_level,
            pain_level=pain_level,
            side_effects=side_effects,
            notes=notes
        )
        
        if result.get('success'):
            return jsonify({'success': True, 'message': 'Symptoms logged successfully'})
        else:
            return jsonify({'error': 'Failed to log symptoms'}), 500

    except Exception as e:
        return jsonify({'error': f'Error logging symptoms: {str(e)}'}), 500

@app.route('/pharmacies')
def pharmacies():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('pharmacies.html')

@app.route('/search_pharmacies')
def search_pharmacies():
    try:
        medication = request.args.get('medication', '').strip()
        if medication:
            pharmacies = db_manager.search_pharmacies_by_medication(medication)
            return jsonify([{
                'id': str(p['_id']),
                'name': p['name'],
                'address': p['address'],
                'phone': p['phone'],
                'delivery_available': p.get('delivery_available', False),
                'inventory': p.get('inventory', [])
            } for p in pharmacies])
        return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        user_role = session['role']
        user_id = session['user_id']
        
        if user_role == 'patient':
            patient = db_manager.get_patient_by_user_id(user_id)
            return render_template('profile.html', profile=patient, role=user_role)
        elif user_role == 'guardian':
            guardian = db_manager.guardians.find_one({"user_id": ObjectId(user_id)})
            return render_template('profile.html', profile=guardian, role=user_role)
        elif user_role == 'pharmacy':
            pharmacy = db_manager.pharmacies.find_one({"user_id": ObjectId(user_id)})
            return render_template('profile.html', profile=pharmacy, role=user_role)
            
    except Exception as e:
        flash(f'Error loading profile: {str(e)}', 'error')
        
    return render_template('profile.html', profile=None, role=session.get('role'))

@app.route('/emergency')
def emergency():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('emergency.html')

# API routes
@app.route('/api/today_schedule')
def api_today_schedule():
    if 'user_id' not in session or session['role'] != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        patient = db_manager.get_patient_by_user_id(session['user_id'])
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        today_meds = db_manager.get_today_medications(str(patient['_id']))
        return jsonify(today_meds)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/compliance')
def api_compliance():
    if 'user_id' not in session or session['role'] != 'patient':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        patient = db_manager.get_patient_by_user_id(session['user_id'])
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        days = request.args.get('days', 7, type=int)
        if days < 1 or days > 365:
            return jsonify({'error': 'Days must be between 1 and 365'}), 400
            
        compliance = db_manager.get_medication_compliance(str(patient['_id']), days)
        return jsonify(compliance)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/guardian_link', methods=['POST'])
def api_guardian_link():
    if 'user_id' not in session or session['role'] != 'guardian':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        guardian_code = data.get('guardian_code', '').strip()
        
        if not guardian_code:
            return jsonify({'error': 'Guardian code is required'}), 400
        
        result = db_manager.link_guardian_to_patient(guardian_code, session['user_id'])
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 400
        else:
            return jsonify({'success': True, 'message': 'Successfully linked to patient'})
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)