from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId
import bcrypt
import os
import random
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        try:
            # MongoDB connection
            self.client = MongoClient('mongodb://localhost:27017/')
            self.db = self.client['mediscan_db']
            
            # Collections
            self.users = self.db.users
            self.patients = self.db.patients
            self.guardians = self.db.guardians
            self.medications = self.db.medications
            self.pharmacies = self.db.pharmacies
            self.medication_logs = self.db.medication_logs
            self.symptoms = self.db.symptoms
            self.guardian_links = self.db.guardian_links
            
            # Initialize indexes for better performance
            self._create_indexes()
            logger.info("Database connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise
    
    def _create_indexes(self):
        """Create database indexes for better performance"""
        try:
            self.users.create_index("email", unique=True)
            self.users.create_index("phone")
            self.patients.create_index("user_id")
            self.patients.create_index("guardian_code", unique=True)
            self.guardians.create_index("user_id")
            self.medications.create_index("patient_id")
            self.pharmacies.create_index("email", unique=True)
            self.medication_logs.create_index([("patient_id", 1), ("date", -1)])
            self.symptoms.create_index([("patient_id", 1), ("date", -1)])
            self.guardian_links.create_index([("patient_id", 1), ("guardian_id", 1)], unique=True)
            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.warning(f"Error creating indexes: {str(e)}")

    # USER MANAGEMENT
    def create_user(self, email, password, role, **kwargs):
        """Create a new user with hashed password"""
        try:
            # Validate input
            if not email or not password or not role:
                return {"error": "Email, password, and role are required"}
            
            if role not in ['patient', 'guardian', 'pharmacy']:
                return {"error": "Invalid role"}
            
            # Check if email already exists
            if self.users.find_one({"email": email}):
                return {"error": "Email already exists"}
            
            # Hash password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            user_data = {
                "email": email,
                "password": hashed_password,
                "role": role,
                "created_at": datetime.utcnow(),
                "is_active": True,
                **kwargs
            }
            
            result = self.users.insert_one(user_data)
            logger.info(f"User created successfully: {email}")
            return {"user_id": str(result.inserted_id)}
            
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return {"error": f"Failed to create user: {str(e)}"}
    
    def authenticate_user(self, email, password):
        """Authenticate user login"""
        try:
            if not email or not password:
                return None
                
            user = self.users.find_one({"email": email, "is_active": True})
            if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
                logger.info(f"User authenticated successfully: {email}")
                return {
                    "user_id": str(user['_id']),
                    "role": user['role'],
                    "email": user['email']
                }
            return None
            
        except Exception as e:
            logger.error(f"Error authenticating user: {str(e)}")
            return None

    # PATIENT MANAGEMENT
    def create_patient_profile(self, user_id, name, age, gender, allergies=None, conditions=None):
        """Create patient profile"""
        try:
            # Validate input
            if not all([user_id, name, age, gender]):
                return {"error": "User ID, name, age, and gender are required"}
            
            if not isinstance(age, int) or age < 0 or age > 150:
                return {"error": "Invalid age"}
            
            # Check if user exists and is a patient
            user = self.users.find_one({"_id": ObjectId(user_id), "role": "patient"})
            if not user:
                return {"error": "Invalid user or user is not a patient"}
            
            # Check if patient profile already exists
            existing_patient = self.patients.find_one({"user_id": ObjectId(user_id)})
            if existing_patient:
                return {"error": "Patient profile already exists"}
            
            patient_data = {
                "user_id": ObjectId(user_id),
                "name": name,
                "age": age,
                "gender": gender,
                "allergies": allergies or [],
                "medical_conditions": conditions or [],
                "guardian_code": self._generate_guardian_code(),
                "created_at": datetime.utcnow()
            }
            
            result = self.patients.insert_one(patient_data)
            logger.info(f"Patient profile created successfully: {name}")
            return {"patient_id": str(result.inserted_id)}
            
        except Exception as e:
            logger.error(f"Error creating patient profile: {str(e)}")
            return {"error": f"Failed to create patient profile: {str(e)}"}
    
    def _generate_guardian_code(self):
        """Generate unique 6-digit code for guardian linking"""
        max_attempts = 10
        for _ in range(max_attempts):
            code = str(random.randint(100000, 999999))
            if not self.patients.find_one({"guardian_code": code}):
                return code
        
        # If we can't find a unique code, use timestamp-based approach
        return str(int(datetime.utcnow().timestamp()))[-6:]
    
    def get_patient_by_user_id(self, user_id):
        """Get patient profile by user ID"""
        try:
            return self.patients.find_one({"user_id": ObjectId(user_id)})
        except Exception as e:
            logger.error(f"Error getting patient by user ID: {str(e)}")
            return None

    # GUARDIAN MANAGEMENT
    def create_guardian_profile(self, user_id, name, phone, relationship):
        """Create guardian profile"""
        try:
            # Validate input
            if not all([user_id, name, phone, relationship]):
                return {"error": "All fields are required"}
            
            # Check if user exists and is a guardian
            user = self.users.find_one({"_id": ObjectId(user_id), "role": "guardian"})
            if not user:
                return {"error": "Invalid user or user is not a guardian"}
            
            # Check if guardian profile already exists
            existing_guardian = self.guardians.find_one({"user_id": ObjectId(user_id)})
            if existing_guardian:
                return {"error": "Guardian profile already exists"}
            
            guardian_data = {
                "user_id": ObjectId(user_id),
                "name": name,
                "phone": phone,
                "relationship": relationship,
                "created_at": datetime.utcnow()
            }
            
            result = self.guardians.insert_one(guardian_data)
            logger.info(f"Guardian profile created successfully: {name}")
            return {"guardian_id": str(result.inserted_id)}
            
        except Exception as e:
            logger.error(f"Error creating guardian profile: {str(e)}")
            return {"error": f"Failed to create guardian profile: {str(e)}"}
    
    def link_guardian_to_patient(self, guardian_code, guardian_user_id):
        """Link guardian to patient using guardian code"""
        try:
            if not guardian_code or not guardian_user_id:
                return {"error": "Guardian code and user ID are required"}
            
            patient = self.patients.find_one({"guardian_code": guardian_code})
            if not patient:
                return {"error": "Invalid guardian code"}
            
            guardian = self.guardians.find_one({"user_id": ObjectId(guardian_user_id)})
            if not guardian:
                return {"error": "Guardian profile not found"}
            
            # Check if link already exists
            existing_link = self.guardian_links.find_one({
                "patient_id": patient['_id'],
                "guardian_id": guardian['_id']
            })
            
            if existing_link:
                return {"error": "Guardian already linked to this patient"}
            
            link_data = {
                "patient_id": patient['_id'],
                "guardian_id": guardian['_id'],
                "linked_at": datetime.utcnow(),
                "is_active": True
            }
            
            result = self.guardian_links.insert_one(link_data)
            logger.info(f"Guardian linked to patient successfully")
            return {"link_id": str(result.inserted_id)}
            
        except Exception as e:
            logger.error(f"Error linking guardian to patient: {str(e)}")
            return {"error": f"Failed to link guardian: {str(e)}"}

    # MEDICATION MANAGEMENT
    # def add_medication(self, patient_id, med_name, dosage, frequency, times, notes=None):
    #     """Add medication to patient's schedule"""
    #     try:
    #         # Validate input
    #         if not all([patient_id, med_name, dosage, frequency, times]):
    #             return {"error": "All required fields must be provided"}
            
    #         if not isinstance(times, list) or len(times) == 0:
    #             return {"error": "At least one time must be specified"}
            
    #         # Validate time format
    #         for time_str in times:
    #             try:
    #                 datetime.strptime(time_str, '%H:%M')
    #             except ValueError:
    #                 return {"error": f"Invalid time format: {time_str}. Use HH:MM format"}
            
    #         # Check if patient exists
    #         patient = self.patients.find_one({"_id": ObjectId(patient_id)})
    #         if not patient:
    #             return {"error": "Patient not found"}
            
    #         medication_data = {
    #             "patient_id": ObjectId(patient_id),
    #             "medication_name": med_name.strip(),
    #             "dosage": dosage.strip(),
    #             "frequency": frequency.strip(),
    #             "times": times,
    #             "notes": notes.strip() if notes else "",
    #             "is_active": True,
    #             "created_at": datetime.utcnow()
    #         }
            
    #         result = self.medications.insert_one(medication_data)
    #         logger.info(f"Medication added successfully: {med_name}")
    #         return {"medication_id": str(result.inserted_id)}
            
    #     except Exception as e:
    #         logger.error(f"Error adding medication: {str(e)}")
    #         return {"error": f"Failed to add medication: {str(e)}"}
    
    #----------Hadi----------
    def add_medication(self, patient_id, med_name, dosage, frequency, times, notes=None, side_effects=None, storage=None, refill_date=None):
        """Add medication to patient's schedule"""
        try:
            # Validate input
            if not all([patient_id, med_name, dosage, frequency, times]):
                return {"error": "All required fields must be provided"}
            
            if not isinstance(times, list) or len(times) == 0:
                return {"error": "At least one time must be specified"}
            
            # Validate time format
            for time_str in times:
                try:
                    datetime.strptime(time_str, '%H:%M')
                except ValueError:
                    return {"error": f"Invalid time format: {time_str}. Use HH:MM format"}
            
            # Check if patient exists
            patient = self.patients.find_one({"_id": ObjectId(patient_id)})
            if not patient:
                return {"error": "Patient not found"}
            
            medication_data = {
                "patient_id": ObjectId(patient_id),
                "medication_name": med_name.strip(),
                "dosage": dosage.strip(),
                "frequency": frequency.strip(),
                "times": times,
                "notes": notes.strip() if notes else "",
                "side_effects": side_effects.strip() if side_effects else "",
                "storage": storage.strip() if storage else "",
                "refill_date": datetime.strptime(refill_date, '%Y-%m-%d') if refill_date else None,
                "is_active": True,
                "created_at": datetime.utcnow()
            }
            
            result = self.medications.insert_one(medication_data)
            logger.info(f"Medication added successfully: {med_name}")
            return {"medication_id": str(result.inserted_id)}
            
        except Exception as e:
            logger.error(f"Error adding medication: {str(e)}")
            return {"error": f"Failed to add medication: {str(e)}"}


    def update_medication(self, medication_id, med_name, dosage, frequency, times, 
                     notes=None, side_effects=None, storage=None, refill_date=None):
        """Update an existing medication"""
        try:
            if not all([medication_id, med_name, dosage, frequency, times]):
                return {"error": "Required fields missing"}
        
            update_data = {
                "medication_name": med_name.strip(),
                "dosage": dosage.strip(),
                "frequency": frequency.strip(),
                "times": times,
                "notes": notes.strip() if notes else "",
                "side_effects": side_effects.strip() if side_effects else "",
                "storage": storage.strip() if storage else "",
                "refill_date": datetime.strptime(refill_date, '%Y-%m-%d') if refill_date else None,
                "updated_at": datetime.utcnow()
            }
        
            result = self.medications.update_one(
                {"_id": ObjectId(medication_id)},
                {"$set": update_data}
            )
        
            if result.modified_count > 0:
                logger.info(f"Medication updated successfully: {med_name}")
                return {"success": True}
            else:
                return {"error": "No medication was updated"}
            
        except Exception as e:
            logger.error(f"Error updating medication: {str(e)}")
            return {"error": f"Failed to update medication: {str(e)}"}

    def delete_medication(self, medication_id):
        """Delete a medication permanently"""
        try:
            result = self.medications.delete_one({"_id": ObjectId(medication_id)})
        
            if result.deleted_count > 0:
                logger.info(f"Medication deleted successfully: {medication_id}")
                return {"success": True}
            else:
                return {"error": "Medication not found"}
            
        except Exception as e:
            logger.error(f"Error deleting medication: {str(e)}")
            return {"error": f"Failed to delete medication: {str(e)}"} 

    
    


    def get_patient_medications(self, patient_id):
        """Get all active medications for a patient"""
        try:
            return list(self.medications.find({
                "patient_id": ObjectId(patient_id),
                "is_active": True
            }))
        except Exception as e:
            logger.error(f"Error getting patient medications: {str(e)}")
            return []

    def update_medication(self, medication_id, **updates):
        """Update medication details"""
        try:
            if not medication_id:
                return {"error": "Medication ID is required"}
            
            # Remove empty values and prepare update data
            update_data = {k: v for k, v in updates.items() if v is not None}
            if not update_data:
                return {"error": "No valid updates provided"}
            
            update_data["updated_at"] = datetime.utcnow()
            
            result = self.medications.update_one(
                {"_id": ObjectId(medication_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"Medication updated successfully: {medication_id}")
                return {"success": True}
            else:
                return {"error": "Medication not found or no changes made"}
                
        except Exception as e:
            logger.error(f"Error updating medication: {str(e)}")
            return {"error": f"Failed to update medication: {str(e)}"}

    def deactivate_medication(self, medication_id):
        """Deactivate a medication"""
        try:
            result = self.medications.update_one(
                {"_id": ObjectId(medication_id)},
                {"$set": {"is_active": False, "deactivated_at": datetime.utcnow()}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Medication deactivated successfully: {medication_id}")
                return {"success": True}
            else:
                return {"error": "Medication not found"}
                
        except Exception as e:
            logger.error(f"Error deactivating medication: {str(e)}")
            return {"error": f"Failed to deactivate medication: {str(e)}"}

    # MEDICATION LOGGING
    def log_medication_taken(self, patient_id, medication_id, taken_at=None):
        """Log when medication was taken"""
        try:
            if not patient_id or not medication_id:
                return {"error": "Patient ID and medication ID are required"}
            
            # Verify medication belongs to patient
            medication = self.medications.find_one({
                "_id": ObjectId(medication_id),
                "patient_id": ObjectId(patient_id),
                "is_active": True
            })
            
            if not medication:
                return {"error": "Medication not found or not active"}
            
            taken_time = taken_at or datetime.utcnow()
            log_data = {
                "patient_id": ObjectId(patient_id),
                "medication_id": ObjectId(medication_id),
                "taken_at": taken_time,
                "date": taken_time.date().isoformat(),
                "status": "taken"
            }
            
            result = self.medication_logs.insert_one(log_data)
            logger.info(f"Medication log created successfully")
            return {"log_id": str(result.inserted_id)}
            
        except Exception as e:
            logger.error(f"Error logging medication: {str(e)}")
            return {"error": f"Failed to log medication: {str(e)}"}
    
    def get_medication_compliance(self, patient_id, days=7):
        """Calculate medication compliance for last N days"""
        try:
            if days < 1 or days > 365:
                return {"error": "Days must be between 1 and 365"}
            
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days-1)  # Include today
            
            # Get logs for the period
            logs = list(self.medication_logs.find({
                "patient_id": ObjectId(patient_id),
                "date": {
                    "$gte": start_date.isoformat(),
                    "$lte": end_date.isoformat()
                }
            }))
            
            # Get patient's active medications
            medications = self.get_patient_medications(patient_id)
            
            if not medications:
                return {
                    "compliance_percentage": 0,
                    "taken_doses": 0,
                    "expected_doses": 0,
                    "message": "No active medications found"
                }
            
            # Calculate expected doses for the period
            expected_doses = 0
            for med in medications:
                daily_doses = len(med.get('times', []))
                expected_doses += daily_doses * days
            
            taken_doses = len(logs)
            compliance = (taken_doses / expected_doses * 100) if expected_doses > 0 else 0
            
            return {
                "compliance_percentage": round(compliance, 1),
                "taken_doses": taken_doses,
                "expected_doses": expected_doses,
                "period_days": days
            }
            
        except Exception as e:
            logger.error(f"Error calculating compliance: {str(e)}")
            return {"error": f"Failed to calculate compliance: {str(e)}"}

    # SYMPTOM TRACKING
    def log_symptom(self, patient_id, mood, energy_level, pain_level, side_effects=None, notes=None):
        """Log daily symptoms and mood"""
        try:
            # Validate input
            if not patient_id:
                return {"error": "Patient ID is required"}
            
            if not all(isinstance(val, int) and 1 <= val <= 10 for val in [mood, energy_level, pain_level]):
                return {"error": "Mood, energy level, and pain level must be integers between 1 and 10"}
            
            # Check if patient exists
            patient = self.patients.find_one({"_id": ObjectId(patient_id)})
            if not patient:
                return {"error": "Patient not found"}
            
            today = datetime.utcnow().date().isoformat()
            symptom_data = {
                "patient_id": ObjectId(patient_id),
                "date": today,
                "mood": mood,
                "energy_level": energy_level,
                "pain_level": pain_level,
                "side_effects": side_effects or [],
                "notes": notes.strip() if notes else "",
                "logged_at": datetime.utcnow()
            }
            
            # Update if entry exists for today, otherwise create new
            result = self.symptoms.update_one(
                {
                    "patient_id": ObjectId(patient_id),
                    "date": today
                },
                {"$set": symptom_data},
                upsert=True
            )
            
            logger.info(f"Symptoms logged successfully for patient: {patient_id}")
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Error logging symptoms: {str(e)}")
            return {"error": f"Failed to log symptoms: {str(e)}"}

    def get_symptom_history(self, patient_id, days=30):
        """Get symptom history for a patient"""
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days-1)
            
            symptoms = list(self.symptoms.find({
                "patient_id": ObjectId(patient_id),
                "date": {
                    "$gte": start_date.isoformat(),
                    "$lte": end_date.isoformat()
                }
            }).sort("date", -1))
            
            # Convert ObjectId to string for JSON serialization
            for symptom in symptoms:
                symptom['_id'] = str(symptom['_id'])
                symptom['patient_id'] = str(symptom['patient_id'])
            
            return symptoms
            
        except Exception as e:
            logger.error(f"Error getting symptom history: {str(e)}")
            return []

    # PHARMACY MANAGEMENT
    def create_pharmacy(self, email, password, name, address, phone, license_number):
        """Create pharmacy account"""
        try:
            # Validate input
            if not all([email, password, name, address, phone, license_number]):
                return {"error": "All fields are required"}
            
            # First create user account
            user_result = self.create_user(email, password, 'pharmacy')
            if 'error' in user_result:
                return user_result
            
            pharmacy_data = {
                "user_id": ObjectId(user_result['user_id']),
                "name": name.strip(),
                "address": address.strip(),
                "phone": phone.strip(),
                "license_number": license_number.strip(),
                "is_verified": False,
                "delivery_available": False,
                "inventory": [],
                "created_at": datetime.utcnow()
            }
            
            result = self.pharmacies.insert_one(pharmacy_data)
            logger.info(f"Pharmacy created successfully: {name}")
            return {"pharmacy_id": str(result.inserted_id)}
            
        except Exception as e:
            logger.error(f"Error creating pharmacy: {str(e)}")
            return {"error": f"Failed to create pharmacy: {str(e)}"}
    
    def add_pharmacy_inventory(self, pharmacy_id, medication_name, price, in_stock=True):
        """Add medication to pharmacy inventory"""
        try:
            if not all([pharmacy_id, medication_name, price]):
                return {"error": "Pharmacy ID, medication name, and price are required"}
            
            if not isinstance(price, (int, float)) or price < 0:
                return {"error": "Price must be a positive number"}
            
            # Check if pharmacy exists
            pharmacy = self.pharmacies.find_one({"_id": ObjectId(pharmacy_id)})
            if not pharmacy:
                return {"error": "Pharmacy not found"}
            
            inventory_item = {
                "medication_name": medication_name.strip(),
                "price": float(price),
                "in_stock": bool(in_stock),
                "updated_at": datetime.utcnow()
            }
            
            # Check if medication already exists in inventory
            existing_med = next((item for item in pharmacy.get('inventory', []) 
                               if item['medication_name'].lower() == medication_name.lower()), None)
            
            if existing_med:
                # Update existing medication
                result = self.pharmacies.update_one(
                    {"_id": ObjectId(pharmacy_id), "inventory.medication_name": existing_med['medication_name']},
                    {"$set": {"inventory.$.price": float(price), 
                             "inventory.$.in_stock": bool(in_stock),
                             "inventory.$.updated_at": datetime.utcnow()}}
                )
            else:
                # Add new medication
                result = self.pharmacies.update_one(
                    {"_id": ObjectId(pharmacy_id)},
                    {"$push": {"inventory": inventory_item}}
                )
            
            if result.modified_count > 0:
                logger.info(f"Pharmacy inventory updated successfully: {medication_name}")
                return {"success": True}
            else:
                return {"error": "Failed to update inventory"}
                
        except Exception as e:
            logger.error(f"Error adding pharmacy inventory: {str(e)}")
            return {"error": f"Failed to add inventory: {str(e)}"}
    
    def search_pharmacies_by_medication(self, medication_name):
        """Search pharmacies that have specific medication in stock"""
        try:
            if not medication_name:
                return []
            
            pharmacies = list(self.pharmacies.find({
                "inventory.medication_name": {"$regex": medication_name.strip(), "$options": "i"},
                "inventory.in_stock": True
            }))
            
            return pharmacies
            
        except Exception as e:
            logger.error(f"Error searching pharmacies: {str(e)}")
            return []

    # UTILITY METHODS
    def get_today_medications(self, patient_id):
        """Get today's medication schedule"""
        try:
            medications = self.get_patient_medications(patient_id)
            if not medications:
                return []
            
            today = datetime.utcnow().date().isoformat()
            
            # Get today's logs
            logs = list(self.medication_logs.find({
                "patient_id": ObjectId(patient_id),
                "date": today
            }))
            
            taken_med_ids = [str(log['medication_id']) for log in logs]
            
            today_schedule = []
            for med in medications:
                for time in med.get('times', []):
                    schedule_item = {
                        "medication_id": str(med['_id']),
                        "medication_name": med['medication_name'],
                        "dosage": med['dosage'],
                        "time": time,
                        "taken": str(med['_id']) in taken_med_ids,
                        "notes": med.get('notes', ''),
                        "frequency": med.get('frequency', '')
                    }
                    today_schedule.append(schedule_item)
            
            # Sort by time
            today_schedule.sort(key=lambda x: x['time'])
            return today_schedule
            
        except Exception as e:
            logger.error(f"Error getting today's medications: {str(e)}")
            return []
    
    def get_patient_guardians(self, patient_id):
        """Get all guardians linked to a patient"""
        try:
            links = list(self.guardian_links.find({
                "patient_id": ObjectId(patient_id),
                "is_active": True
            }))
            
            guardians = []
            for link in links:
                guardian = self.guardians.find_one({"_id": link['guardian_id']})
                if guardian:
                    guardian['_id'] = str(guardian['_id'])
                    guardian['user_id'] = str(guardian['user_id'])
                    guardians.append(guardian)
            
            return guardians
            
        except Exception as e:
            logger.error(f"Error getting patient guardians: {str(e)}")
            return []

    def get_guardian_patients(self, guardian_user_id):
        """Get all patients linked to a guardian"""
        try:
            guardian = self.guardians.find_one({"user_id": ObjectId(guardian_user_id)})
            if not guardian:
                return []
            
            links = list(self.guardian_links.find({
                "guardian_id": guardian['_id'],
                "is_active": True
            }))
            
            patients = []
            for link in links:
                patient = self.patients.find_one({"_id": link['patient_id']})
                if patient:
                    patient['_id'] = str(patient['_id'])
                    patient['user_id'] = str(patient['user_id'])
                    patients.append(patient)
            
            return patients
            
        except Exception as e:
            logger.error(f"Error getting guardian patients: {str(e)}")
            return []

    # DATABASE HEALTH CHECK
    def health_check(self):
        """Check database connection and basic functionality"""
        try:
            # Test connection
            self.client.admin.command('ping')
            
            # Test basic operations
            test_collections = [
                self.users, self.patients, self.guardians, 
                self.medications, self.pharmacies, self.medication_logs, 
                self.symptoms, self.guardian_links
            ]
            
            for collection in test_collections:
                collection.find_one()
            
            return {"status": "healthy", "timestamp": datetime.utcnow()}
            
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {"status": "unhealthy", "error": str(e), "timestamp": datetime.utcnow()}

# Initialize database instance
try:
    db_manager = DatabaseManager()
except Exception as e:
    logger.error(f"Failed to initialize database manager: {str(e)}")
    raise

# Sample data insertion function for testing
def insert_sample_data():
    """Insert sample data for testing"""
    try:
        logger.info("Inserting sample data...")
        
        # Create sample patient
        user_result = db_manager.create_user(
            email="patient@test.com",
            password="password123",
            role="patient",
            name="John Doe"
        )
        
        if 'user_id' in user_result:
            patient_result = db_manager.create_patient_profile(
                user_id=user_result['user_id'],
                name="John Doe",
                age=35,
                gender="Male",
                allergies=["Penicillin"],
                conditions=["Diabetes", "Hypertension"]
            )
            
            if 'patient_id' in patient_result:
                # Add sample medications
                med1_result = db_manager.add_medication(
                    patient_id=patient_result['patient_id'],
                    med_name="Metformin",
                    dosage="500mg",
                    frequency="daily",
                    times=["08:00", "20:00"],
                    notes="Take with food"
                )
                
                med2_result = db_manager.add_medication(
                    patient_id=patient_result['patient_id'],
                    med_name="Lisinopril",
                    dosage="10mg",
                    frequency="daily",
                    times=["08:00"],
                    notes="Monitor blood pressure"
                )
                
                logger.info(f"Sample medications added: {med1_result}, {med2_result}")
        
        # Create sample guardian
        guardian_user_result = db_manager.create_user(
            email="guardian@test.com",
            password="guardian123",
            role="guardian",
            name="Jane Doe"
        )
        
        if 'user_id' in guardian_user_result:
            guardian_result = db_manager.create_guardian_profile(
                user_id=guardian_user_result['user_id'],
                name="Jane Doe",
                phone="+1234567890",
                relationship="Spouse"
            )
            logger.info(f"Sample guardian created: {guardian_result}")
        
        # Create sample pharmacy
        pharmacy_result = db_manager.create_pharmacy(
            email="pharmacy@test.com",
            password="pharmacy123",
            name="MediCare Pharmacy",
            address="123 Health Street, Medical City",
            phone="+1234567890",
            license_number="PH123456"
        )
        
        if 'pharmacy_id' in pharmacy_result:
            # Add inventory
            inv1_result = db_manager.add_pharmacy_inventory(
                pharmacy_id=pharmacy_result['pharmacy_id'],
                medication_name="Metformin",
                price=25.50
            )
            
            inv2_result = db_manager.add_pharmacy_inventory(
                pharmacy_id=pharmacy_result['pharmacy_id'],
                medication_name="Lisinopril",
                price=15.75
            )
            
            logger.info(f"Sample pharmacy inventory added: {inv1_result}, {inv2_result}")
        
        logger.info("Sample data inserted successfully!")
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error inserting sample data: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    # Run health check
    health = db_manager.health_check()
    logger.info(f"Database health: {health}")
    
    # Insert sample data if requested
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--sample-data":
        insert_sample_data()