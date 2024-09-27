import anvil.server
import base64
import mysql.connector
from mysql.connector import Error
from ultralytics import YOLO
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
import io
import pymysql.cursors
import logging
import numpy as np
import pandas as pd
import datetime 
from decimal import Decimal  # Import Decimal for precise decimal arithmetic

#  Load the pre-trained YOLO model
model_path = r'C:\Users\Mangales\Desktop\App\fastapi-anvil\myenv\best.pt'
model = YOLO(model_path)

# Connect to Anvil Uplink
anvil.server.connect("server_IOWUOSI44HSF3N6E5SOYPSWC-I5OU23DJFFSG245Z")

@anvil.server.callable 
def get_min_max_dates():
    connection = create_connection()
    if not connection:
        return {"status": "error", "message": "Database connection failed"}

    try:
        with connection.cursor() as cursor:
            # SQL query to get the min and max dates
            query = """
                SELECT MIN(DATE(processed_dt)) AS min_date,
                        MAX(DATE(processed_dt)) AS max_date
                FROM potholes_detected;
            """
            cursor.execute(query)
            result = cursor.fetchone()
            
            # Ensure the query returned valid results
            if result:
                min_date = result[0]
                max_date = result[1]
                return min_date, max_date
            else:
                raise ValueError("No dates found in the database.")
            
    except pymysql.MySQLError as e:
        print(f"Database query error: {str(e)}")
        return {"status": "error", "message": f"Database query error: {str(e)}"}

    finally:
        if connection:
            connection.close()


@anvil.server.callable
##Code for testing passing values back to Anvil##

# def get_stats():
#     # Assuming you get these values from a database or calculations
#     total_images = 41  # Replace with your actual calculation
#     potholes_detected = 6  # Replace with your actual calculation
    
#     # Return the two values directly
#     return total_images, potholes_detected

#Code for testing passing values back to Anvil##

# Function to get average max confidence score
@anvil.server.callable
def get_avg_max_conf_score():
    # Establish the database connection
    connection = create_connection()
    
    # If connection fails, return an error message
    if not connection:
        return {"status": "error", "message": "Database connection failed"}

    try:
        with connection.cursor() as cursor:
            # Query to get the average of max confidence scores
            query = """
                SELECT AVG(max_conf_score)
                FROM potholes_detected
            """
            cursor.execute(query)
            avg_max_conf_score = cursor.fetchone()[0]  # Fetch the result

            # If no data is found, handle that case
            if avg_max_conf_score is None:
                avg_max_conf_score = Decimal(0.0)  # Set to Decimal(0.0) for consistency

            # Convert Decimal to float for serialization
            avg_max_conf_score = float(avg_max_conf_score)

            return {"status": "success", "avg_max_conf_score": avg_max_conf_score}

    except pymysql.MySQLError as e:
        logging.error(f"Database error: {e}")
        return {"status": "error", "message": str(e)}  # Return error message
    
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return {"status": "error", "message": str(e)}  # Handle general exceptions
    
    finally:
        # Ensure the connection is closed even if an error occurs
        if connection:
            connection.close()

##################
## Bubble Chart ##
##################

@anvil.server.callable
def get_pothole_bubble_data():
    connection = create_connection()
    if not connection:
        return {"status": "error", "message": "Database connection failed"}

    try:
        with connection.cursor() as cursor:
            # Query to get incidents, their pothole counts, and average confidence scores
            query = """
                SELECT potholes_count, COUNT(*) AS frequency, AVG(max_conf_score) AS avg_conf_score
                FROM potholes_detected
                GROUP BY potholes_count
            """
            cursor.execute(query)
            data = cursor.fetchall()
            
            # Structure the data for returning
            pothole_counts = []
            frequencies = []
            avg_conf_scores = []
            for row in data:
                pothole_counts.append(row[0])  # Number of potholes detected
                frequencies.append(row[1])  # Frequency of incidents
                avg_conf_scores.append(float(row[2]) if row[2] is not None else 0.0)  # Convert to float
            return {
                "status": "success",
                "pothole_counts": pothole_counts,
                "frequencies": frequencies,
                "avg_conf_scores": avg_conf_scores
            }

    except pymysql.MySQLError as e:
        logging.error(f"Database error: {e}")
        return {"status": "error", "message": str(e)}

    except Exception as e:
            logging.error(f"An error occurred: {e}")
            return {"status": "error", "message": str(e)}

    finally:
        if connection:
            connection.close()



####### Pie Chart #########

def get_pie_plot():
    connection = create_connection()
    if not connection:
        return {"status": "error", "message": "Database connection failed"}

    try:
        print("Inside get pie plot try")
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
                
                print(f"total_images: {total_images} and total potholes detected is: {potholes_detected}")
                print(f"total images now is of thye: {type(total_images)}")

            #  # Extract values and convert to integers
                # total_images = int(total_images_result['total_images'])
                # potholes_detected = int(potholes_detected_result['potholes_detected'])
                # potholes_not_detected = total_images - potholes_detected

                return {#{"status": "error", "message": "Unexpected result format"}
                    "status": "success",
                    "data":(total_images, potholes_detected)
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


        return total_images, potholes_detected
        
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

#########################
### Potholes vs. Time ###
#########################

@anvil.server.callable
def get_pothole_trends():
    # Create database connection
    connection = create_connection()
    if not connection:
        return {"status": "error", "message": "Database connection failed"}

    try:
        print("Fetching pothole trends data")
        
        with connection.cursor(dictionary=True) as cursor:
            query_potholes_trend = """
            SELECT DATE(processed_dt) AS detection_date, 
                   SUM(potholes_count) AS total_potholes_count
            FROM potholes_detected
            GROUP BY DATE(processed_dt)
            ORDER BY detection_date ASC;
            """
            cursor.execute(query_potholes_trend)
            result = cursor.fetchall()
            
            if not result:
                return {"status": "error", "message": "No data available"}
            
            # Convert Decimal to float for serializing
            for row in result:
                row['total_potholes_count'] = float(row['total_potholes_count'])
            
            return {"status": "success", "data": result}
    
    except mysql.connector.Error as err:
        logging.error(f"SQL execution error: {err}")
        return {"status": "error", "message": "Failed to execute SQL query"}
    
    except Exception as e:
        logging.error(f"Error in fetching pothole trends: {str(e)}")
        return {"status": "error", "message": "Error fetching data"}
    
#####################
## HEAT MAP & BAR CHART: Potholes Severity  
#####################

@anvil.server.callable
def get_severity_data():
    conn = create_connection()
    cursor = conn.cursor()

    # Query to get the confidence scores
    query = "SELECT max_conf_score FROM potholes_detected"
    cursor.execute(query)

    # Fetch all results
    results = cursor.fetchall()
    
    # Convert results to a DataFrame
    scores = pd.DataFrame(results, columns=['max_conf_score'])
    
    # Group scores into categories
    conditions = [
        (scores['max_conf_score'] < 0.33),
        (scores['max_conf_score'] >= 0.33) & (scores['max_conf_score'] < 0.66),
        (scores['max_conf_score'] >= 0.66)
    ]
    choices = ['Low', 'Medium', 'High']
    scores['Severity'] = np.select(conditions, choices)

    # Group by severity
    heatmap_data = scores.groupby('Severity').size().reset_index(name='Counts')

    return heatmap_data.to_dict(orient='records')

#####################
## Feedback Received vs. Number of Poholes detected by date
#####################
@anvil.server.callable
def get_pothole_feedback_data(date_from=None, date_to=None):
    try:
        conn = create_connection()
        cursor = conn.cursor()

        #  Get min and max dates if not provided
        cursor.execute("SELECT MIN(processed_dt), MAX(processed_dt) FROM potholes_detected")
        min_date, max_date = cursor.fetchone()

        # If no dates are provided, use the min and max dates from the database
        if date_from is None:
            date_from = min_date
        if date_to is None:
            date_to = max_date

        # Ensure dates are in correct format
        date_from = date_from.strftime('%Y-%m-%d')
        date_to = date_to.strftime('%Y-%m-%d')

        # Query for potholes count
        potholes_query = f"""
            SELECT DATE(processed_dt) as detection_date, COUNT(*) as potholes_count 
            FROM potholes_detected
            WHERE processed_dt BETWEEN '{date_from}' AND '{date_to}'
            GROUP BY detection_date
            ORDER BY detection_date
        """
        cursor.execute(potholes_query)
        potholes_data = cursor.fetchall()

        # Query for feedback count
        feedback_query = f"""
            SELECT DATE(review_dt) as feedback_date, COUNT(*) as feedback_count
            FROM potholes_undetected
            WHERE review_dt BETWEEN '{date_from}' AND '{date_to}'
            GROUP BY feedback_date
            ORDER BY feedback_date
        """
        cursor.execute(feedback_query)
        feedback_data = cursor.fetchall()

        conn.close()

        # Convert results to DataFrames for easy plotting
        potholes_df = pd.DataFrame(potholes_data, columns=['date', 'potholes_count'])
        feedback_df = pd.DataFrame(feedback_data, columns=['date', 'feedback_count'])

        # Merge the two datasets on the date
        merged_data = pd.merge(potholes_df, feedback_df, on='date', how='outer').fillna(0)

        return merged_data.to_dict(orient='records')

    except Exception as e:
        print(f"Error fetching data: {e}")
        return []

###################
## double line graph - feedbk, potholes detected vs. date
###################
@anvil.server.callable
def get_daily_feedback_and_potholes():
    conn = create_connection()
    cursor = conn.cursor()
    
    try:
        query = """
        SELECT 
            DATE(updated_at) AS feedback_date, 
            COUNT(id) AS feedback_count, 
            SUM(potholes_count) AS total_potholes_detected
        FROM 
            image_data
        WHERE 
            updated_at IS NOT NULL
        GROUP BY 
            DATE(updated_at)
        ORDER BY 
            feedback_date;
        """
    
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Ensure conversion of potential 'Decimal' types to 'int'
        formatted_results = []
        for row in results:
            formatted_results.append({
                "feedback_date": row[0],
                "feedback_count": int(row[1]),  # Ensuring feedback_count is an int
                "total_potholes_detected": int(row[2])  # Ensuring total_potholes_detected is an int
            })
        
        return formatted_results
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return []  # Return an empty list or handle the error as needed

    finally:
        cursor.close()  # Ensure the cursor is closed
        conn.close()    # Ensure the connection is closed


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