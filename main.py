import pytesseract
from PIL import Image
import streamlit as st
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
import pandas as pd
import re
import base64
from io import BytesIO

# Environment variables
language_key = 'd59c070ceefa417687e0b85ddf37a7c8'
language_endpoint = 'https://lang097867575.cognitiveservices.azure.com/'

# Authenticate the client using your key and endpoint
def authenticate_client():
    ta_credential = AzureKeyCredential(language_key)
    text_analytics_client = TextAnalyticsClient(
        endpoint=language_endpoint, 
        credential=ta_credential)
    return text_analytics_client

client = authenticate_client()

# Function to extract text from image using Tesseract-OCR
def extract_text_from_image(image):
    text = pytesseract.image_to_string(image)
    return text

# Function to detect PII information from text
def detect_pii(text):
    documents = [text]
    response = client.recognize_pii_entities(documents, language="en")
    result = [doc for doc in response if not doc.is_error]
    pii_entities = []
    for doc in result:
        for entity in doc.entities:
            pii_entities.append({
                "text": entity.text,
                "category": entity.category,
                "confidence_score": entity.confidence_score,
                "offset": entity.offset,
                "length": entity.length
            })
    return pii_entities

# Function to mask PII information in text
def mask_pii(text, pii_entities):
    for entity in pii_entities:
        if entity["category"] == "PhoneNumber":
            masked_text = text[:entity["offset"]] + entity["text"][:3] + "*" * (entity["length"] - 3) + text[entity["offset"] + entity["length"]:]
            text = masked_text
        elif entity["category"] == "Email":
            # Mask the email to show only the first two characters of the username and mask the rest
            username, domain = entity["text"].split("@")
            masked_email = username[:2] + "*" * (len(username) - 2) + "@" + "*" * len(domain)
            masked_text = text[:entity["offset"]] + masked_email + text[entity["offset"] + entity["length"]:]
            text = masked_text
    return text

# Function to extract department from text using regex
def extract_department(text):
    department_keywords = ['Production', 'Marketing', 'Sales', 'Finance', 'Human Resources', 'Engineering']
    
    # Find the department by checking if any department keyword is present in the text
    for keyword in department_keywords:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
            return keyword
    return "Unknown"

# Function to create a clickable image
def create_clickable_image(image_file):
    img = Image.open(image_file)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f'<img src="data:image/png;base64,{img_str}" style="width:100px; height:auto;" onclick="window.open(this.src)" />'

# Streamlit interface
st.title("Data Sentinel: Azure's PII Looker")

with st.container():
    image_files = st.file_uploader("Upload one or more images of employee ID cards", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

st.markdown("<h1 style='text-align: center; color: blue;'>Masked Employee Details</h1>", unsafe_allow_html=True)

# Function to extract and mask details, then return a DataFrame with all details
def extract_and_mask_details(image_files):
    data = []
    
    for i, image_file in enumerate(image_files):
        # Extract text from each image
        image = Image.open(image_file)
        text = extract_text_from_image(image)
        
        # Detect PII and mask details
        pii_entities = detect_pii(text)
        masked_text = mask_pii(text, pii_entities)
        
        # Extract details
        name = next((entity['text'] for entity in pii_entities if entity['category'] == 'Person'), 'N/A')
        mobile_number = next((entity['text'][:3] + '*' * (len(entity['text']) - 3) for entity in pii_entities if entity['category'] == 'PhoneNumber'), 'N/A')
        email_id = next((entity['text'].split('@')[0][:2] + '*' * (len(entity['text'].split('@')[0]) - 2) + '@' + '*' * len(entity['text'].split('@')[1]) for entity in pii_entities if entity['category'] == 'Email'), 'N/A')

        # Extract department from text
        department = extract_department(text)

        # Create clickable image
        image_link = create_clickable_image(image_file)

        # Append extracted details with a serial number
        data.append({
            'Serial Number': i + 1,
            'Name': name,
            'Department': department,
            'Mobile Number': mobile_number,
            'Email ID': email_id,
            'Image': image_link  # Add clickable image directly
        })

    # Convert to DataFrame for tabular display
    df = pd.DataFrame(data)
    return df

# Display the results in a table
if image_files:
    result_df = extract_and_mask_details(image_files)

    # Convert DataFrame to HTML with clickable images
    st.write(result_df.to_html(escape=False, index=False), unsafe_allow_html=True)

    # Add functionality for image preview
    image_clicked = st.selectbox("Select an image to preview:", options=[f"Image {i+1}" for i in range(len(image_files))], format_func=lambda x: result_df['Name'][int(x.split()[-1])-1])
    
    if image_clicked:
        selected_index = int(image_clicked.split()[-1]) - 1
        st.session_state.selected_image = image_files[selected_index]
    
    if 'selected_image' in st.session_state and st.session_state.selected_image:
        st.image(st.session_state.selected_image, caption='Preview', width=200)  # Adjust the width for the preview image