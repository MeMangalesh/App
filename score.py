import anvil.server
import base64
import mysql.connector
from mysql.connector import Error
from mysql.connector.cursor import MySQLCursorDict  # Import the dictionary cursor
from ultralytics import YOLO
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
import io
import os
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
  
##############################
## NEWLY ADDED FOR DETECTION & SCORE      
##############################
# Helper functions
@anvil.server.callable
def fetch_image_by_id(image_id):
    # Import your create_connection function
    connection = create_connection()  # Establish the DB connection only when the function is called
    try:
        with connection.cursor(dictionary=True) as cursor:
            print("inside fetch_image_by_id function")
            sql = "SELECT pothole_detected, potholes_count, encode_base64 FROM image_data WHERE id = %s"
            cursor.execute(sql, (image_id,))
            result = cursor.fetchone()

            return result
    finally:
        connection.close()  # Make sure to close the connection after usage


def decode_image(encoded_image):
    image_data = base64.b64decode(encoded_image)
    print("inside decode_image function")
    return Image.open(io.BytesIO(image_data))

def perform_pothole_detection(image):
    print("inside perform pothole detcetion function")
    results = model(image)  # YOLOv8 detection
    return results

def calculate_confidence_and_area(results):
    print("inside  calculate_confidence_and_area function ")
    
    pothole_detected = False
    potholes_count = 0
    max_conf_score = 0.0
    min_conf_score = None
    max_pothole_area = 0.0
    min_pothole_area = None
    
     # Iterate over all results (detections)
    for result in results:
        if result.boxes:  # Ensure there are bounding boxes in the result
            pothole_detected = True
            potholes_count += len(result.boxes)  # Count the number of detected potholes
            print(f"Potholes detected: {potholes_count}")
            
            for box in result.boxes:  # Iterate over each detected pothole (box)
                #Ensure the box has the correct xywh format (4 values: x, y, width, height)
                if box.xywh.size(1) == 4:  # Ensure correct dimension size
                    conf_score = float(box.conf.item())  # Convert tensor to Python float
                    width = float(box.xywh[0, 2].item())  # Extract width
                    height = float(box.xywh[0, 3].item())  # Extract height
                    area = width * height  # Calculate area

                    print(f"Box confidence score: {conf_score}")
                    print(f"Box coordinates (xywh): {box.xywh}")
                    print(f"Confidence score: {conf_score}")
                    print(f"Area: {area}")

                    # Update max and min confidence scores
                    max_conf_score = max(max_conf_score, conf_score)
                    if min_conf_score is None or conf_score < min_conf_score:
                        min_conf_score = conf_score

                    # Update max and min areas
                    max_pothole_area = max(max_pothole_area, area)
                    if min_pothole_area is None or area < min_pothole_area:
                        min_pothole_area = area
                else:
                    print(f"Error: box.xywh does not have the expected size. xywh={box.xywh}")
    
    # If only one pothole is detected, set the min values to the same as the max values
    if potholes_count == 1:
        min_conf_score = max_conf_score
        min_pothole_area = max_pothole_area

    # Handle cases where no valid confidence score or area was found
    if min_conf_score is None:
        min_conf_score = 0.0  # Default minimum confidence score
    if min_pothole_area is None:
        min_pothole_area = 0.0  # Default minimum area

    # Print the calculated values for debugging purposes
    print(f"Minimum conf score: {min_conf_score}")
    print(f"Maximum conf score: {max_conf_score}")
    print(f"Minimum pothole area: {min_pothole_area}")
    print(f"Maximum pothole area: {max_pothole_area}")
    print(f"Potholes count: {potholes_count}")
    
    # Generate annotated image
    # result_img_pil = generate_annotated_image(results)

    # if isinstance(result_img_pil, Image.Image):  # Ensure result_img_pil is a PIL Image
    #     buffered = io.BytesIO()
    #     result_img_pil.save(buffered, format="PNG")
    #     processed_image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    # else:
    #     print("Error: result_img_pil is not a PIL Image.")
    #     processed_image_base64 = None

    processed_image_base64 = 50

    # Return the calculated values
    return pothole_detected, potholes_count, max_conf_score, min_conf_score, max_pothole_area, min_pothole_area


@anvil.server.callable
def detect_potholescore_with_ID(image_id):
    print("Value of image_id:", image_id)
    print("Type of image_id:", type(image_id))

    try:
        connection = create_connection()
        
        # Retrieve the image from the database using the image ID
        result = fetch_image_by_id(image_id)
        
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

        # Print results
        print(f"potholes dteected: {pothole_detected}")
        print(f"potholes count: {potholes_count}")
        print(f"max conf score: {max_conf_score}")
        print(f"max pothole area:{max_pothole_area}")

        ##Generate annotated image
        # result_img_pil = (results)
        # print("returned from generate_annotated_image function")
        # if isinstance(result_img_pil, Image.Image):  # Ensure result_img_pil is a PIL Image
        #     buffered = io.BytesIO()
        #     result_img_pil.save(buffered, format="PNG")
        #     processed_image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        # else:
        #     print("Error: result_img_pil is not a PIL Image.")
        #     processed_image_base64 = None
        


        processed_image_base64 = 50

        # Update the database with the detection results
        with connection.cursor() as cursor:
            print("Updating the image_data tbl with processed results")
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

        return pothole_detected, potholes_count, max_conf_score, min_conf_score, max_pothole_area, min_pothole_area

    except Exception as e:
        print(f"Error detecting potholes: {e}")
        return None, None, None
    

##################################################################
### Code below commented to test the function with same name added on 22 Sept 2024
# ############################################################## 

# def generate_annotated_image(results):
#     # Create a blank image or use an existing image
#     width, height = 640, 640  # Example dimensions
#     image = Image.new('RGB', (width, height), (255, 255, 255))  # Create a white image

#     # Specify the folder and file path
#     folder_path = "C:\\Users\\Mangales\\Desktop\\App\\fastapi-anvil"
#     file_path = os.path.join(folder_path, "output_image_with_boxes.png")

#     # Draw bounding boxes on the image
#     draw = ImageDraw.Draw(image)
#     print("In generate annotated image function")

#     # Create the folder if it doesn't exist
#     if not os.path.exists(folder_path):
#         os.makedirs(folder_path)
#         print(f"Directory '{folder_path}' created successfully")

#     # Iterate over all detection results
#     for result in results:
#         if result.boxes:  # Ensure there are bounding boxes in the result
#             print(f"Found {len(result.boxes)} bounding boxes.")

#             # Iterate over each detected bounding box
#             for box in result.boxes:
#                 # Ensure the bounding box has the expected xywh format with 4 values
#                 if box.xywh.shape[-1] == 4:
#                     # Extract the xywh from the tensor and convert it to a list
#                     xywh = box.xywh.squeeze().tolist()

#                     # Now we have a list of 4 values we can unpack
#                     x_center, y_center, width, height = xywh

#                     # Calculate bounding box corners
#                     x1 = x_center - width / 2
#                     y1 = y_center - height / 2
#                     x2 = x_center + width / 2
#                     y2 = y_center + height / 2

#                     # Save the image to check visually
#                     image.save("file_path")
#                     print("Image saved successfully")
#                 else:
#                     # Handle cases where xywh does not have exactly 4 values
#                     print(f"Skipping box with unexpected xywh format: {box.xywh}")

#     return image




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