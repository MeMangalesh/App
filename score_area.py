import anvil.server
import base64
import mysql.connector
from mysql.connector import Error
from mysql.connector.cursor import MySQLCursorDict  # Import the dictionary cursor
from ultralytics import YOLO
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
import io
import datetime
#added the import below for displaying data in table
import pymysql.cursors

# Load the pre-trained YOLO model
model_path = r'C:\Users\Mangales\Desktop\App\fastapi-anvil\myenv\best.pt'
model = YOLO(model_path)

# Connect to Anvil Uplink
anvil.server.connect("server_IOWUOSI44HSF3N6E5SOYPSWC-I5OU23DJFFSG245Z")

@anvil.server.callable
def get_data():
    connection = create_connection()
    if not connection:
        return {"status": "error", "message": "Database connection failed"}

    # print("In get_data() function of VSCode")

    try:
        # Use cursor to execute query
        cursor = connection.cursor(dictionary=True)  # Use dictionary=True for dict cursor
        query = """
        SELECT id, filename, url, created_at, updated_at, pothole_detected, potholes_count 
        FROM image_data
        """
        cursor.execute(query)
        result = cursor.fetchall()
        #  print(result)  # Debugging: Print the result to check the data
        ### Added the code below
        # Convert datetime objects to strings
        for row in result:
            if isinstance(row['created_at'], datetime.datetime):
                row['created_at'] = row['created_at'].strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(row['updated_at'], datetime.datetime):
                row['updated_at'] = row['updated_at'].strftime("%Y-%m-%d %H:%M:%S")
        
       # print(result)  # Debugging: Print the result to check the modified data
        ### Added code ends here
        return {"status": "success", "data": result}
    
    except Error as e:
        print(f"Database error: {e}")
        return {"status": "error", "message": f"Database error: {e}"}
    
    finally:
        connection.close()

# Function to save image to database
def save_image_to_db(image_base64, filename):
    connection = create_connection()
    if not connection:
        return {"status": "error", "message": "Database connection failed"}

    cursor = connection.cursor()
    try:
        query = """
        INSERT INTO image_data (encode_base64, filename, created_at, updated_at, pothole_detected, potholes_count)
        VALUES (%s, %s, NOW(), NOW(), %s, %s)
        """
        values = (image_base64, filename, 0, 0)
        cursor.execute(query, values)
        connection.commit()
        return {"status": "success"}
    except Error as e:
        connection.rollback()
        return {"status": "error", "message": f"Database error: {e}"}
    finally:
        cursor.close()
        connection.close()
#######################
## Newly added functions
#######################

# Helper functions
def fetch_image_by_id(connection, image_id):
    with connection.cursor(dictionary=True) as cursor:
        sql = "SELECT encode_base64 FROM image_data WHERE id = %s"
        cursor.execute(sql, (image_id,))
        return cursor.fetchone()

def decode_image(encoded_image):
    image_data = base64.b64decode(encoded_image)
    return Image.open(io.BytesIO(image_data))

def perform_pothole_detection(image):
    results = model(image)  # YOLOv8 detection
    return results

def calculate_confidence_and_area(results):
    pothole_detected = False
    potholes_count = 0
    max_conf_score = 0.0
    min_conf_score = float('inf')
    max_pothole_area = 0.0
    min_pothole_area = float('inf')

    for result in results:
        if result.boxes:
            pothole_detected = True
            potholes_count += len(result.boxes)

            for box in result.boxes:
                conf_score = box.conf.item()
                area = box.xywh[2] * box.xywh[3]

                max_conf_score = max(max_conf_score, conf_score)
                min_conf_score = min(min_conf_score, conf_score)

                max_pothole_area = max(max_pothole_area, area)
                min_pothole_area = min(min_pothole_area, area)

    if potholes_count == 1:
        min_conf_score = max_conf_score
        min_pothole_area = max_pothole_area

    return pothole_detected, potholes_count, max_conf_score, min_conf_score, max_pothole_area, min_pothole_area

def generate_annotated_image(results):
    if results:
        result_img = results[0].plot()
        result_img_pil = Image.fromarray(result_img)
        return result_img_pil
    return None

# Anvil Uplink callable function
@anvil.server.callable
def save_image_n_trigger_detection(image_base64, filename):
    try:
        connection = create_connection()
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO image_data (filename, encode_base64)
                VALUES (%s, %s)
            """
            cursor.execute(sql, (filename, image_base64))
            connection.commit()
            
            # Get the ID of the newly inserted image
            image_id = cursor.lastrowid
            print(f"the id of the newly saved image in sintd function is: {image_id}")
            return image_id
    except Exception as e:
        print(f"Error saving image: {e}")
        return None

# Save image and trigger detection
@anvil.server.callable
def save_image_n_trigger_detection(image_base64, filename):
    try:
        connection = create_connection()

        # Save image into the database
        with connection.cursor() as cursor:
            sql = """
                INSERT INTO image_data (filename, encode_base64)
                VALUES (%s, %s)
            """
            cursor.execute(sql, (filename, image_base64))
            connection.commit()

            # Get the ID of the newly inserted image
            image_id = cursor.lastrowid
            print(f"the id of the newly saved image in save_image_n_trigger_detection function is: {image_id}")

        # Trigger pothole detection using the saved image ID
        pothole_detected, potholes_count, processed_image_base64 = detect_potholes_with_ID(image_id)

        if pothole_detected:
            print(f"Potholes detected: {potholes_count}")

        return image_id

    except Exception as e:
        print(f"Error saving image and triggering detection: {e}")
        return None

@anvil.server.callable
def detect_potholes_with_ID(image_id):
    print("Value of image_id:", image_id)
    print("Type of image_id:", type(image_id))

    try:
        connection = create_connection()
        
        # Retrieve the image from the database using the image ID
        result = fetch_image_by_id(connection, image_id)
        
        if not result:
            return None  # Image not found
        
        encoded_image = result['encode_base64']
        print("Fetched encoded image")

        # Decode the base64 image
        image = decode_image(encoded_image)
        
        # Convert the image to RGB if it's not already (YOLO expects RGB format)
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Perform pothole detection using YOLOv8
        results = perform_pothole_detection(image)

        # Calculate confidence scores and areas
        pothole_detected, potholes_count, max_conf_score, min_conf_score, max_pothole_area, min_pothole_area = calculate_confidence_and_area(results)

        # Generate annotated image
        result_img_pil = generate_annotated_image(results)

        if result_img_pil:
            buffered = io.BytesIO()
            result_img_pil.save(buffered, format="PNG")
            processed_image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        else:
            processed_image_base64 = None

        # Update the database with the detection results
        with connection.cursor() as cursor:
            print("Updating the image_data with processed results")
            sql = """
                UPDATE image_data
                SET pothole_detected = %s, potholes_count = %s, updated_at = NOW()
                WHERE id = %s
            """
            cursor.execute(sql, (pothole_detected, potholes_count, image_id))
            connection.commit()

        # Insert the detection results into the appropriate table
        with connection.cursor() as cursor:
            if pothole_detected:
                sql = """
                    INSERT INTO potholes_detected (image_id, processed_image_base64, potholes_count,
                                                   max_conf_score, min_conf_score, 
                                                   max_pothole_area, min_pothole_area, processed_dt)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """
                cursor.execute(sql, (image_id, processed_image_base64, potholes_count,
                                     max_conf_score, min_conf_score, max_pothole_area, min_pothole_area))
            else:
                sql = """
                    INSERT INTO potholes_undetected (image_id, processed_image_base64, processed_dt)
                    VALUES (%s, %s, NOW())
                """
                cursor.execute(sql, (image_id, processed_image_base64))
            
            connection.commit()

        return pothole_detected, potholes_count, processed_image_base64

    except Exception as e:
        print(f"Error detecting potholes: {e}")
        return None




#########
### old functions
# ############## 
# @anvil.server.callable
# def detect_potholes_with_ID(image_id):
#     # Print the value and type of image_id for debugging
#     print("Value of image_id:", image_id)
#     print("Type of image_id:", type(image_id))

#     try:
#         connection = create_connection()
        
#         # Retrieve the image from the database using the image ID
#         with connection.cursor(dictionary=True) as cursor:  # Use dictionary cursor
#             sql = "SELECT encode_base64 FROM image_data WHERE id = %s"
#             cursor.execute(sql, (image_id,))
#             result = cursor.fetchone()
            
#             if not result:
#                 return None  # Image not found
            
#             encoded_image = result['encode_base64']
#             print("fetched encoded image")

#         # Decode the base64 image
#         image_data = base64.b64decode(encoded_image)
#         # Load the image using Pillow
#         image = Image.open(io.BytesIO(image_data))
        
#         # Convert the image to RGB if it's not already (YOLO expects RGB format)
#         if image.mode != 'RGB':
#             image = image.convert('RGB')

#         # Perform pothole detection using YOLOv8
#         results = model(image)  # YOLOv8 accepts a PIL Image object

#           # Initialize detection flags
#         pothole_detected = False
#         potholes_count = 0
#         result_img_pil = None

#         # Iterate over the results and check for the pothole class
#         for result in results:
#             # Assuming `result` is your output from YOLO
#             result_img = result.plot()  # Get the annotated image as a NumPy array

#             # Convert the NumPy array to a PIL Image
#             result_img_pil = Image.fromarray(result_img)

#             if result.boxes:
#                 pothole_detected = True
#                 potholes_count += len(result.boxes)

#         # Convert the PIL Image to bytes
#         if result_img_pil is not None:
#             buffered = io.BytesIO()
#             result_img_pil.save(buffered, format="PNG")
#             image_bytes = buffered.getvalue()

#             # Encode the image bytes to base64
#             processed_image_base64 = base64.b64encode(image_bytes).decode('utf-8')
#         else:
#             processed_image_base64 = None

#         # Update the database with the detection results
#         with connection.cursor() as cursor:
#             print("about to update the image_data with processed results")
#             sql = """
#                 UPDATE image_data
#                 SET pothole_detected = %s, potholes_count = %s, updated_at = NOW()
#                 WHERE id = %s
#             """
#             cursor.execute(sql, (pothole_detected, potholes_count, image_id))
#             connection.commit()

#             print(f"pothole detected YN: {pothole_detected}")

#         # Insert the detected pothole results into a separate table
#         if not pothole_detected:
#             with connection.cursor() as cursor:
#                 print("about to insert detected pothole images into detection results table")
#                 sql_1 = """
#                     INSERT INTO potholes_undetected (image_id, processed_image_base64, processed_dt)
#                     VALUES (%s, %s, NOW())
#                 """
#                 cursor.execute(sql_1, (image_id, processed_image_base64))
#                 connection.commit()

#         return pothole_detected, potholes_count, processed_image_base64
    
#     except Exception as e:
#         print(f"Error detecting potholes: {e}")
#         return None
#########
### old functions
# ############## 

######################
####  DATABASE    ####
######################

# Database connection function
def create_connection():
    try:
        connection = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="dbpodv1",
            database="potholes"
        )
        return connection
    except Error as e:
        print(f"The error '{e}' occurred")
        return None

# Execute Query 
def execute_query(connection, query):
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        connection.commit()
        print("Query executed successfully")
    except Error as e:
        print(f"The error '{e}' occurred")

# Keep the script running
anvil.server.wait_forever()