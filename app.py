import pandas as pd
import streamlit as st
import requests
from io import BytesIO
import base64
from datetime import datetime
from streamlit_pdf_viewer import pdf_viewer
import re

# Set page configuration
st.set_page_config(
    page_title="Vehicle Documentation Viewer",
    layout="wide"
)

# Function to get year range
def get_year_range():
    current_year = datetime.now().year
    return list(range(current_year, 1980, -1))  # From current year down to 1950

# Function to clean string for filename
def clean_filename(text):
    # Remove special characters and replace spaces with underscores
    cleaned = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
    cleaned = cleaned.replace(' ', '_')
    return cleaned

# Function to fetch data from NHTSA API with pagination
@st.cache_data
def fetch_nhtsa_data(year):
    all_data = pd.DataFrame()
    page = 1
    
    while True:
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/GetParts?type=565&fromDate=1/1/{year}&toDate=12/31/{year}&format=csv&page={page}"
        try:
            df = pd.read_csv(url)
            
            # If we get an empty dataframe, we've reached the end
            if df.empty:
                break
                
            # Concatenate the new data
            all_data = pd.concat([all_data, df], ignore_index=True)
            
            # Move to next page
            page += 1
            
        except Exception as e:
            st.error(f"Error fetching data for page {page}: {str(e)}")
            break
    
    if all_data.empty:
        st.warning(f"No data found for year {year}")
    else:
        st.success(f"Found {len(all_data)} records across {page-1} pages")
    
    return all_data

# Sidebar filters
st.sidebar.title("Filter Options")

# Initialize session state for selections if not already present
if 'selected_year' not in st.session_state:
    st.session_state.selected_year = None
if 'selected_make' not in st.session_state:
    st.session_state.selected_make = None
if 'selected_version' not in st.session_state:
    st.session_state.selected_version = None
if 'nhtsa_data' not in st.session_state:
    st.session_state.nhtsa_data = None
if 'pdf_bytes' not in st.session_state:
    st.session_state.pdf_bytes = None

# Get years from current year to 1950
years = get_year_range()

# Year selection
selected_year = st.sidebar.selectbox(
    "Select Year",
    years,
    index=None if st.session_state.selected_year is None else years.index(st.session_state.selected_year) if st.session_state.selected_year in years else None,
    placeholder="Choose a year..."
)

# Update session state and fetch data when year changes
if selected_year != st.session_state.selected_year:
    st.session_state.selected_year = selected_year
    st.session_state.selected_make = None
    st.session_state.selected_version = None
    st.session_state.nhtsa_data = fetch_nhtsa_data(selected_year)
    st.session_state.pdf_bytes = None

# Make selection (only if year is selected and data is loaded)
if selected_year is not None and st.session_state.nhtsa_data is not None and not st.session_state.nhtsa_data.empty:
    # Get unique manufacturer names
    makes = sorted(st.session_state.nhtsa_data['manufacturername'].unique())
    
    selected_make = st.sidebar.selectbox(
        "Select Make",
        makes,
        index=None if st.session_state.selected_make is None else makes.index(st.session_state.selected_make) if st.session_state.selected_make in makes else None,
        placeholder="Choose a make..."
    )
    
    # Update session state
    if selected_make != st.session_state.selected_make:
        st.session_state.selected_make = selected_make
        st.session_state.selected_version = None
        st.session_state.pdf_bytes = None
    
    # Version selection (only if make is selected)
    if selected_make is not None:
        # Filter data for selected make and sort by letterdate in descending order
        make_data = st.session_state.nhtsa_data[st.session_state.nhtsa_data['manufacturername'] == selected_make]
        make_data = make_data.sort_values('letterdate', ascending=False)
        
        # Create version options from the filtered data
        versions = make_data.apply(lambda x: f"{x['name']} ({x['letterdate']})", axis=1).tolist()
        
        selected_version = st.sidebar.selectbox(
            "Select Version",
            versions,
            index=None if st.session_state.selected_version is None else versions.index(st.session_state.selected_version) if st.session_state.selected_version in versions else None,
            placeholder="Choose a version..."
        )
        
        # Update session state
        if selected_version != st.session_state.selected_version:
            st.session_state.selected_version = selected_version
            st.session_state.pdf_bytes = None

# Main content area
st.title("Vehicle Documentation Viewer")

# Display filtered results only if all selections are made
if selected_year is not None and selected_make is not None and selected_version is not None:
    # Get the selected version's data
    version_name = selected_version.split(" (")[0]  # Extract name from version string
    version_data = make_data[make_data['name'] == version_name].iloc[0]
    
    st.write(f"Showing documentation for {selected_year} {selected_make} - {version_name}")
    
    # Get the PDF URL
    pdf_url = version_data['url']
    
    try:
        # Add buttons to sidebar
        st.sidebar.markdown("---")  # Add a separator
        st.sidebar.markdown("### Document Actions")
        
        # Open in new tab button
        st.sidebar.markdown(f'<a href="{pdf_url}" target="_blank" style="text-decoration: none;"><button style="width: 100%; padding: 10px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">Open PDF in New Tab</button></a>', unsafe_allow_html=True)
        
        # Try to fetch and display the PDF
        if st.session_state.pdf_bytes is None:
            response = requests.get(pdf_url)
            if response.status_code == 200:
                st.session_state.pdf_bytes = response.content
            else:
                st.warning(f"Could not fetch PDF from URL. Status code: {response.status_code}")
                st.info("Please use the 'Open PDF in New Tab' link above to view the documentation.")
                st.session_state.pdf_bytes = None
        
        # Download button (only if we have the PDF)
        if st.session_state.pdf_bytes is not None:
            # Create a clean filename
            clean_version = clean_filename(version_name)
            clean_make = clean_filename(selected_make)
            filename = f"{selected_year}_{clean_make}_{clean_version}.pdf"
            
            st.sidebar.download_button(
                label="Download PDF",
                data=st.session_state.pdf_bytes,
                file_name=filename,
                mime="application/pdf"
            )
            
            # Show PDF using streamlit-pdf-viewer
            # Using 90% width to ensure proper rendering and some margin
            # Height is set to 800px for good visibility
            pdf_viewer(
                st.session_state.pdf_bytes,
                width="90%",
                height=auto,
                pages_vertical_spacing=2
            )
        else:
            st.error("Could not load PDF. Please try opening in a new tab.")
            
    except Exception as e:
        st.error(f"Error accessing PDF: {str(e)}")
        st.info("Please use the 'Open PDF in New Tab' link above to view the documentation.")
else:
    st.info("Please select a year, make, and version from the sidebar to view documentation.")





