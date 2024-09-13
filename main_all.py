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

# # Anvil Uplink callable function
# @anvil.server.callable
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

# Anvil Uplink callable function
@anvil.server.callable
def save_image(image_base64, filename):
    return save_image_to_db(image_base64, filename)

########################
##  START ADMIN FORM  ##
########################

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

# Anvil Uplink callable function
@anvil.server.callable
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

@anvil.server.callable
def detect_potholes_with_ID(image_id):
    # Print the value and type of image_id for debugging
    print("Value of image_id:", image_id)
    print("Type of image_id:", type(image_id))

    try:
        connection = create_connection()
        
        # Retrieve the image from the database using the image ID
        with connection.cursor(dictionary=True) as cursor:  # Use dictionary cursor
            sql = "SELECT encode_base64 FROM image_data WHERE id = %s"
            cursor.execute(sql, (image_id,))
            result = cursor.fetchone()
            
            if not result:
                return None  # Image not found
            
            encoded_image = result['encode_base64']
            print("fetched encoded image")

        # Decode the base64 image
        image_data = base64.b64decode(encoded_image)
        # Load the image using Pillow
        image = Image.open(io.BytesIO(image_data))
        
        # Convert the image to RGB if it's not already (YOLO expects RGB format)
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Perform pothole detection using YOLOv8
        results = model(image)  # YOLOv8 accepts a PIL Image object

          # Initialize detection flags
        pothole_detected = False
        potholes_count = 0
        result_img_pil = None

        # Iterate over the results and check for the pothole class
        for result in results:
            # Assuming `result` is your output from YOLO
            result_img = result.plot()  # Get the annotated image as a NumPy array

            # Convert the NumPy array to a PIL Image
            result_img_pil = Image.fromarray(result_img)

            if result.boxes:
                pothole_detected = True
                potholes_count += len(result.boxes)

        # Convert the PIL Image to bytes
        if result_img_pil is not None:
            buffered = io.BytesIO()
            result_img_pil.save(buffered, format="PNG")
            image_bytes = buffered.getvalue()

            # Encode the image bytes to base64
            processed_image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        else:
            processed_image_base64 = None

        # Update the database with the detection results
        with connection.cursor() as cursor:
            print("about to update the image_data with processed results")
            sql = """
                UPDATE image_data
                SET pothole_detected = %s, potholes_count = %s, updated_at = NOW()
                WHERE id = %s
            """
            cursor.execute(sql, (pothole_detected, potholes_count, image_id))
            connection.commit()

            print(f"pothole detected YN: {pothole_detected}")

        # Insert the detected pothole results into a separate table
        if not pothole_detected:
            with connection.cursor() as cursor:
                print("about to insert detected pothole images into detection results table")
                sql_1 = """
                    INSERT INTO potholes_undetected (image_id, processed_image_base64, processed_dt)
                    VALUES (%s, %s, NOW())
                """
                cursor.execute(sql_1, (image_id, processed_image_base64))
                connection.commit()

        return pothole_detected, potholes_count, processed_image_base64
    
    except Exception as e:
        print(f"Error detecting potholes: {e}")
        return None
  

###############################
##   START DETECT POTHOLES  ###
###############################

@anvil.server.callable
# Function to detect potholes in an image
def detect_potholes(image_base64, filename):
    try:
        # Decode the base64 image
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))

        # Convert the image to RGB if it's not already
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Perform detection using the YOLO model
        results = model(image)

        # Process each result in the list 
        # Parse the detection results
        pothole_detected = False
        potholes_count = 0
        result_img_pil = None  # To store the final image

        # Iterate over the results and check for the pothole class
        for result in results:
            # Assuming `result` is your output from YOLO
            result_img = result.plot()  # Get the annotated image as a NumPy array

            # Convert the NumPy array to a PIL Image
            result_img_pil = Image.fromarray(result_img)  # Convert to PIL Image
            
            if result.boxes:
                pothole_detected = True
                potholes_count += len(result.boxes)
                #print(f"Iteration: {result} , pothole_detected: {pothole_detected}, pothole_count: {potholes_count}")
       
        # Convert the PIL Image to bytes
        if result_img_pil is not None:
            buffered = io.BytesIO()
            result_img_pil.save(buffered, format="PNG")
            image_bytes = buffered.getvalue()

            # Encode the image bytes to base64
            processed_image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        else:
            processed_image_base64 = None
        return pothole_detected, potholes_count, processed_image_base64

    except Exception as e:
        print(f"Error in detect_potholes: {e}")
        return []

#######################
## START REVIEW FORM ##
##### Get images  #####
#######################

@anvil.server.callable
def get_images():
    connection = create_connection()
    if not connection:
        return {"status": "error", "message": "Database connection failed"}

    try:
        print("inside get images vscode function")
        # Use cursor to execute query
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT image_id, processed_image_base64
        FROM potholes_undetected
        WHERE pothole_detected = 0
        """
        cursor.execute(query)
        result = cursor.fetchall()

        decoded_results = [{
            'id': row['image_id'],
            'image_base64': row['processed_image_base64']            
        } for row in result]

        print("Outside decoded results for loop")
        return {"status": "success", "data": decoded_results}
    
    except pymysql.Error as e:
        print(f"Database error: {e}")
        return {"status": "error", "message": f"Database error: {e}"}
    
    finally:
        connection.close()    

########################
##     REVIEW FORM    ##
### Get data by date ###
########################

# get_data based on date filter
@anvil.server.callable
def get_data_by_date(start_date, end_date):
    connection = create_connection()
    if not connection:
        return {"status": "error", "message": "Database connection failed"}

    try:
        # Use cursor to execute query
        cursor = connection.cursor(dictionary=True)  # Use dictionary=True for dict cursor
        
        # Convert start_date and end_date to include time
        if isinstance(start_date, datetime.date):
            start_date = datetime.datetime.combine(start_date, datetime.time.min)  # Start at 12:00 AM
        if isinstance(end_date, datetime.date):
            end_date = datetime.datetime.combine(end_date, datetime.time.max)  # End at 11:59:59 PM
        
        # Ensure the dates are formatted correctly
        start_date_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
        end_date_str = end_date.strftime("%Y-%m-%d %H:%M:%S")

        query = """
        SELECT image_id, processed_image_base64
        FROM potholes_undetected
        WHERE pothole_detected = 0 AND
        processed_dt BETWEEN %s AND %s
        """
        cursor.execute(query, (start_date_str, end_date_str))
        result = cursor.fetchall()

        # # Convert datetime objects to strings
        # for row in result:
        #     if isinstance(row['created_at'], datetime.datetime):
        #         row['created_at'] = row['created_at'].strftime("%Y-%m-%d %H:%M:%S")
        #     if isinstance(row['updated_at'], datetime.datetime):
        #         row['updated_at'] = row['updated_at'].strftime("%Y-%m-%d %H:%M:%S")

                
        decoded_results = [{
            'id': row['image_id'],
            'image_base64': row['processed_image_base64']            
        } for row in result]

        return {"status": "success", "data": decoded_results}
    
    except pymysql.Error as e:
        print(f"Database error: {e}")
        return {"status": "error", "message": f"Database error: {e}"}
    
    finally:
        connection.close()

##########################
## START DASHBOARD FORM ##
##########################

# Anvil Uplink callable function
@anvil.server.callable
def get_statistics():
    connection = create_connection()
    if not connection:
        return {"status": "error", "message": "Database connection failed"}

    try:
        print("Inside get statistics try")
        # Use DictCursor specifically for this query
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # Query to count total images
            query_total_images = """
            SELECT count(*) as total_images FROM image_data
            """
            cursor.execute(query_total_images)
            total_images_result = cursor.fetchone()

            # Query to count images with potholes detected
            query_potholes_detected = """
            SELECT count(*) as potholes_detected FROM image_data WHERE pothole_detected = 1
            """
            cursor.execute(query_potholes_detected)
            potholes_detected_result = cursor.fetchone()

            #####Check type
            
            print(f"type of total_images_result: {type(total_images_result)}, value: {total_images_result}")
            print(f"type of potholes_detected_result: {type(potholes_detected_result)}, value: {potholes_detected_result}")

            # Convert tuple results to integers
            if isinstance(total_images_result, tuple) and isinstance(potholes_detected_result, tuple):
                print("Inside isinstance")
                # Assign values to variables
                total_images = int(total_images_result[0])
                potholes_detected = int(potholes_detected_result[0])
                
                print(f"type of total_images: {total_images} and the type is: {type(total_images)}")

            #  # Extract values and convert to integers
                # total_images = int(total_images_result['total_images'])
                # potholes_detected = int(potholes_detected_result['potholes_detected'])
                # potholes_not_detected = total_images - potholes_detected

                return {#{"status": "error", "message": "Unexpected result format"}
                    "status": "success",
                    "data":(total_images, potholes_detected, )
                }

            else:
                # If results are not tuples
                print("Results are not in tuple format")
                # return {#{"status": "error", "message": "Unexpected result format"}
                #     "status": "success",
                #     "data":(total_images, potholes_detected, potholes_not_detected)
                # }
                # print(f"type of total_images_result after converting to int: {type(total_images)}, value: {total_images}")
                # print(f"type of potholes_detected_result after converting to int: {type(potholes_detected)}, value: {potholes_detected}")
                # print(f"potholes_not_detected : {type(potholes_not_detected)}, value: {potholes_not_detected}")


        #return total_images, potholes_detected, potholes_not_detected
        
            #### end check type

            #     # Ensure results are tuples
            # if isinstance(total_images_result, tuple) and isinstance(potholes_detected_result, tuple):
            #     # Assign values to variables
            #     total_images = total_images_result[0]
            #     potholes_detected = potholes_detected_result[0]
            #     potholes_not_detected = total_images - potholes_detected

            #     print(f"total images processed: {total_images}")
            #     print(f"total potholes detected: {potholes_detected}")
            #     #print(f"total not potholes detected: {potholes_not_detected}")
                
            #     return total_images, potholes_detected #, potholes_not_detected
            # else:
            #     return {"status": "error", "message": "Unexpected result format"}

    except pymysql.Error as e:
        return {"status": "error", "message": f"Database error: {e}"}
    finally:
        if connection:
            connection.close()

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
