import streamlit as st
from streamlit_folium import folium_static
import folium
from folium.plugins import MarkerCluster
from folium.map import Icon
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
import os
import plotly.express as px
from geopy.distance import great_circle
import locale
from PIL import Image

# Page Configuration
st.set_page_config(page_title="Apartment Rent Prediction", layout="wide")

# Add custom CSS for adjusting the zoom level
st.markdown(
    """
    <style>
        body {
            zoom: 90%;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Title
st.title("Apartment Rent Prediction Dashboard")

# Set the locale to the user's default locale
locale.setlocale(locale.LC_ALL, '')

@st.cache_data
def load_data(file_path):
    return pd.read_excel(file_path, sheet_name="Data for regression")

# Display your logo in the sidebar
logo_path = r"C:\Users\DCL\Desktop\fiverr\sean-pollock-PhYq704ffdA-unsplash.jpg"

try:
    logo_image = Image.open(logo_path)
    st.sidebar.image(logo_image, width=200)
except Exception as e:
    st.error(f"Error loading the logo: {e}")

# Sidebar
st.sidebar.title("Input Property Data")
selected_city = st.sidebar.selectbox("Select City", options=['Berlin', 'Munich', 'Frankfurt', 'Hamburg', 'Cologne'])

# Load data based on the selected city using the cached function
data_files = {
    'Berlin': r"C:\Users\DCL\Desktop\fiverr\Berlin Data Final V3.xlsx",
    'Munich': r"C:\Users\DCL\Desktop\fiverr\Munich Data Final V3.xlsx",
    'Frankfurt': r"C:\Users\DCL\Desktop\fiverr\Frankfurt Data Final V3.xlsx",
    'Hamburg': r"C:\Users\DCL\Desktop\fiverr\Hamburg Data Final V3.xlsx",
    'Cologne': r"C:\Users\DCL\Desktop\fiverr\Cologne Data Final V3.xlsx",
}

df = load_data(data_files[selected_city])
# Drop rows with NaN values in latitude or longitude columns
df = df.dropna(subset=['Latitude', 'Longitude'])

@st.cache_data
def read_city_data(city):
    file_path = data_files[city]
    data = pd.read_excel(file_path, sheet_name='Data for regression')
    avg_price = data['Price/Night'].mean()
    avg_min_nights = data['Minimum Nights'].mean()
    return avg_price, avg_min_nights

# Coordinates for city centers
city_centers = {
    'Berlin': {'lat': 52.5162, 'lon': 13.3777},
    'Munich': {'lat': 48.1372, 'lon': 11.5755},
    'Frankfurt': {'lat': 50.1109, 'lon': 8.6821},
    'Cologne': {'lat': 50.9372, 'lon': 6.9614},
    'Hamburg': {'lat': 53.5511, 'lon': 9.9937},
}

# Coefficients for each city
coefficients = {
    'Munich': {'intercept': 5.172101, 'type': 28.343488, 'ln_distance': -30.807145, 'guests': 18.239103,
               'bedrooms': 25.475162, 'bathrooms': 52.063975, 'ac': 21.311525},
    'Berlin': {'intercept': -9.077806, 'type': 58.797374, 'ln_distance': -18.231469, 'guests': 6.2406919,
               'bedrooms': 26.751278, 'bathrooms': 48.799936, 'ac': 46.506289},
    'Frankfurt': {'intercept': 30.456818, 'type': 36.419622, 'ln_distance': -14.018948, 'guests': 14.867489,
                  'bedrooms': 5.936328, 'bathrooms': 20.236058, 'ac': 19.173738},
    'Cologne': {'intercept': -6.270858, 'type': 70.973393, 'ln_distance': -8.873988, 'guests': 2.979441,
                'bedrooms': 50.539905, 'bathrooms': 17.31529, 'ac': 47.106795},
    'Hamburg': {'intercept': 40.010260, 'type': 44.342464, 'ln_distance': -11.155349, 'guests': 11.809334,
                 'bedrooms': 12.649841, 'bathrooms': 6.052979, 'ac': 21.879238}
}

# Define color intervals for Price/Night with explanations
price_colors = {
    (0, 50): {'color': 'darkgreen', 'label': '0-50 EUR'},
    (50, 100): {'color': 'gold', 'label': '50-100 EUR'},
    (100, 200): {'color': 'orange', 'label': '100-200 EUR'},
    (200, 1000): {'color': 'tomato', 'label': '200-1000 EUR'}
}

# Calculate distance using Haversine formula
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0  # Radius of the Earth in km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    distance = R * c
    return distance

# Assuming you have a dictionary containing average occupancy rates for each city
average_occupancy_rates = {
    'Berlin': 66,
    'Frankfurt': 39,
    'Munich': 48,
    'Hamburg': 64,
    'Cologne': 53
}

@st.cache_data
def get_lat_lon_from_address(address):
    geolocator = Nominatim(user_agent="your_app_name")
    location = geolocator.geocode(address, country_codes="DE")
    if location:
        return location.latitude, location.longitude
    else:
        return None, None


# Input widgets for rent prediction
user_address = st.sidebar.text_input("Address")
room_type = st.sidebar.selectbox("Room Type", options=["Full Flat", "Single Room"])
num_bedrooms = st.sidebar.number_input("Number of Bedrooms", min_value=0)
num_bathrooms = st.sidebar.number_input("Number of Bathrooms", min_value=0)
num_guests = st.sidebar.number_input("Number of Guests", min_value=0)
ac = st.sidebar.checkbox("Air Conditioning")
predict_toggle_col1 = st.sidebar.toggle('**Predict Rent**')


# Function to create and initialize the map
def create_map(user_address=None):
    map_center = [df['Latitude'].mean(), df['Longitude'].mean()]
    mymap = folium.Map(location=map_center, zoom_start=12)

    # Add Marker Cluster
    marker_cluster = MarkerCluster().add_to(mymap)

    # Add markers for each Airbnb listing with color-coded circles
    for index, row in df.iterrows():
        # Format Airbnb type for display
        airbnb_type = row['AirBnB type'].replace('_', ' ').title()

        popup_text = f"Price/Night: {row['Price/Night']} EUR<br>" \
                     f"Type: {airbnb_type}<br>" \
                     f"URL: <a href='{row['Url']}' target='_blank'>Link</a><br>"

        # Include only desired amenities in the popup
        desired_amenities = ['AC', 'WIFI', 'Kitchen', 'Free parking on the property', 'TV']
        for amenity in desired_amenities:
            popup_text += f"{amenity}: {'&#10004;' if row[amenity] == 1 else '&#10008;'}<br>"

        color = next((color_info['color'] for price_range, color_info in price_colors.items() if
                      price_range[0] <= row['Price/Night'] < price_range[1]), 'grey')

        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=5,
            popup=folium.Popup(popup_text, max_width=300),
            color=color,
            fill=True,
            fill_color=color
        ).add_to(marker_cluster)

    # Add a legend to the map
    legend_html = '<div style="position: fixed; bottom: 10px; left: 10px; z-index: 1000; background-color: white; padding: 10px; border: 1px solid grey;">'
    legend_html += '<b>Price Intervals:</b><br>'
    for price_range, color_info in price_colors.items():
        legend_html += f'<div style="background-color: {color_info["color"]}; width: 15px; height: 15px; display: inline-block;"></div> {color_info["label"]}<br>'
    legend_html += '</div>'
    mymap.get_root().html.add_child(folium.Element(legend_html))

    user_lat, user_lon = None, None  # Initialize with default values

    # Check and add marker for user address
    if user_address:
        user_lat, user_lon = get_lat_lon_from_address(user_address)
        if user_lat and user_lon:
            folium.Marker(
                location=[user_lat, user_lon],
                popup=f'User Entered Address: {user_address}',
                icon=folium.Icon(color='red')
            ).add_to(mymap)

            # Update map center and zoom based on the user's address
            mymap.location = [user_lat, user_lon]
            mymap.zoom_start = 15

    return mymap, user_lat, user_lon


# Row 1: Map and Rent Prediction
col1, col2 = st.columns([8,4])  # Creating two columns in the first row

with col1:
    # Create and display the map, and get user_lat and user_lon
    mymap, user_lat, user_lon = create_map(user_address if user_address else None)
    folium_static(mymap)

    # Display a smaller header for the legend
    st.markdown("##### Price Intervals Legend:")
    legend_cols = st.columns(4)  # Create 4 mini-columns for the legend items

    legend_info = [
        ("darkgreen", "0-50 EUR"),
        ("gold", "50-100 EUR"),
        ("orange", "100-200 EUR"),
        ("tomato", "200-1000 EUR")
    ]

    for idx, (color, desc) in enumerate(legend_info):
        with legend_cols[idx]:
            st.markdown(f"<div style='display: flex; align-items: center;'>\
                <div style='background-color: {color}; height: 15px; width: 15px; margin-right: 5px;'></div>{desc}\
                </div>", unsafe_allow_html=True)


with col2:
    if predict_toggle_col1:  # Check if the Predict Rent toggle is clicked
        # Rent prediction
        if room_type is not None and num_bedrooms != 0 and \
                num_bathrooms != 0 and num_guests != 0 and ac is not None and user_lat is not None and user_lon is not None:
            distance = calculate_distance(user_lat, user_lon, city_centers[selected_city]['lat'],
                                          city_centers[selected_city]['lon'])
            rent_prediction = round(
                    coefficients[selected_city]['intercept']
                    + coefficients[selected_city]['type'] * (room_type == 'Full Flat')
                    + coefficients[selected_city]['ln_distance'] * np.log(distance + 1)
                    + coefficients[selected_city]['guests'] * num_guests
                    + coefficients[selected_city]['bedrooms'] * num_bedrooms
                    + coefficients[selected_city]['bathrooms'] * num_bathrooms
                    + coefficients[selected_city]['ac'] * ac
            )
        else: rent_prediction = 0

        # Display a small header for Total Income
        st.markdown("##### Rent per Night")

        container8 = st.container(border=True)

        # Format the predicted rent with a comma for thousands and a comma instead of a dot for decimals
        formatted_rent_prediction = locale.format_string("%.2f", rent_prediction, grouping=True).replace('.', ',')

        # Display predicted rent
        if rent_prediction == 0:
            container8.error("Please fill out all the inputs.", icon="⚠️")
        else:
            # Display the formatted predicted rent and average price with commas and the Euro sign after the number
            container8.write(f"**Your expected Rent per Night: {formatted_rent_prediction} €**")

        # Format the average price with a comma for thousands and a comma instead of a dot for decimals
        avg_price, avg_min_nights = read_city_data(selected_city)
        formatted_avg_price = locale.format_string("%.2f", avg_price, grouping=True).replace('.', ',')

        # Display the formatted average price with commas and the Euro sign after the number
        container8.write(f"ø Price per Night in {selected_city}: {formatted_avg_price} €")

        st.write("")
        st.write("")

        #Check if predicted rent is not 0
        if rent_prediction != 0:

            # Display a small header for Total Income
            st.markdown("##### Total Annual Income Potential")

            # Create tabs
            tab1, tab2 = st.tabs(["**Occupancy Rate in %**", "**Occupancy in Days**"])

            with tab1:
                container1 = st.container(border=True)

                # Averag Occupancy rate per city
                container1.write(f"ø Occupancy Rate for {selected_city} is {average_occupancy_rates[selected_city]} %.")

                # Set the initial value of the slider to the average occupancy rate for the selected city
                initial_slider_value = average_occupancy_rates.get(selected_city, 50)

                # Add a slider inside the container
                percentage_slider = container1.slider("What is your expected occupancy rate per year in percent?", 0,
                                                      100, initial_slider_value)

                # Add a styled divider with reduced spacing above
                container1.markdown("<hr style='margin-top: 0; margin-bottom: 20; border-left: 1px solid #ddd;'>",
                                    unsafe_allow_html=True)

                # Calculate total income potential
                total_income_potential1 = percentage_slider / 100 * 365 * rent_prediction

                # Format the total income potential with commas for thousands
                formatted_total_income = locale.format_string("%.2f", total_income_potential1, grouping=True)

                # Display the total income potential with commas
                container1.write(f"Total Annual Income Potential for your Property: **{formatted_total_income} €**")

            with tab2:
                container2 = st.container(border=True)

                # Add a number input inside the container
                selected_days = container2.number_input(
                    "How many days per year will your property be available for rent?", min_value=0, max_value=365,
                    value=7)

                # Add a styled divider with reduced spacing above
                container2.markdown("<hr style='margin-top: 0; margin-bottom: 20; border-left: 1px solid #ddd;'>",
                                    unsafe_allow_html=True)

                # Calculate total income potential
                total_income_potential2 = selected_days * rent_prediction

                # Format the total income potential with commas for thousands
                formatted_total_income = locale.format_string("%.2f", total_income_potential2, grouping=True)

                # Display the total income potential with commas
                container2.write(f"Total Annual Income Potential for your Property: **{formatted_total_income} €**")

if predict_toggle_col1:  # Check if the Predict Rent toggle is clicked
    # Add a line to separate rows
    st.divider()

    # Streamlit widgets for price range input
    min_price, max_price = st.slider('Select Price Range', min_value=int(df['Price/Night'].min()),
                                     max_value=int(df['Price/Night'].max()),
                                     value=(int(df['Price/Night'].min()), int(df['Price/Night'].max())))


    def filter_by_price_range(data_frame, min_price, max_price):
        """
        Filter the DataFrame based on a given price range.

        Parameters:
        data_frame (DataFrame): The original pandas DataFrame.
        min_price (int): The minimum price.
        max_price (int): The maximum price.

        Returns:
        DataFrame: The filtered DataFrame.
        """
        return data_frame[(data_frame['Price/Night'] >= min_price) & (data_frame['Price/Night'] <= max_price)]


    # Update the dashboard based on the price range inputs
    filtered_data = filter_by_price_range(df, min_price, max_price)

    # Row 2: Filtering Section
    col1, col2 = st.columns(2)

    with col1:
        # Titel
        st.subheader("Similar properties in this price range")

        # Apply custom CSS for progress bar color and adjust spacing
        st.markdown(
            """
            <style>
                .stProgress > div > div > div > div {
                    background-color: darkgrey;
                }
                .symbol-div {
                    margin-right: 5px;
                }
                .text-div {
                    margin-right: 50px;
                }
            </style>""",
            unsafe_allow_html=True,
        )

        # Calculate the percentage of listings with each amenity
        amenities = ['AC', 'WIFI', 'Kitchen', 'Free parking on the property', 'TV']
        percentages = [filtered_data[amenity].mean() * 100 for amenity in amenities]

        # Display progress bars with icons on the left side and percentage at the end
        for percentage, amenity in zip(percentages, amenities):
            symbol = ''
            if amenity == 'WIFI':
                symbol = '🛜'  # WiFi symbol
            elif amenity == 'Kitchen':
                symbol = '🍳'  # Kitchen symbol
            elif amenity == 'AC':
                symbol = '❄️'  # AC symbol
            elif amenity == 'TV':
                symbol = '📺'  # TV symbol
            elif amenity == 'Free parking on the property':
                symbol = '🚗'  # Car symbol

            # Display progress bar with icon and percentage at the end
            progress_text = f"<div style='display: flex; align-items: center;'><div class='symbol-div'>{symbol}</div> <div class='text-div'>{amenity}: {percentage:.1f}%</div></div>"
            st.markdown(progress_text, unsafe_allow_html=True)
            st.progress(percentage / 100)

            # Add a line break for spacing
            st.markdown("<br>", unsafe_allow_html=True)

    with col2:
        st.subheader("Minimum Nights Analysis")
        st.write(f"ø Minimum Nights in {selected_city}: {avg_min_nights:.2f}")

        # Process the data for the column chart using filtered data
        # Grouping minimum nights > 5 into a '6+' category in the filtered data
        filtered_data['Minimum Nights Categorized'] = filtered_data['Minimum Nights'].apply(
            lambda x: str(x) if x <= 6 else '6+')
        df_grouped = filtered_data['Minimum Nights Categorized'].value_counts(normalize=True).round(2).reset_index()
        df_grouped.columns = ['Minimum Nights', 'Percentage']

        # Create the Plotly column chart
        fig = px.bar(
            df_grouped,
            x='Minimum Nights',
            y='Percentage',
            labels={'Percentage': 'Percentage of Listings'},
            text='Percentage',
            color_discrete_sequence=['#ff9c89']
        )

        # Customize the layout
        fig.update_layout(
            xaxis_title='Minimum Nights',
            yaxis_title='Percentage of Listings',
            showlegend=True,
            legend_title_text='Legend',
            yaxis=dict(tickformat='.0%'),  # Format y-axis ticks as whole number percentages
            xaxis={'categoryorder': 'total descending'}  # Sorting the x-axis categories
        )

        # Add custom x-axis labels for values 1 to 6
        fig.update_xaxes(
            ticktext=['1', '2', '3', '4', '5', '6+'],
            tickvals=['1', '2', '3', '4', '5', '6']
        )

        # Streamlit code to display the chart
        st.plotly_chart(fig, use_container_width=True)

    # Add a line to separate rows
    st.markdown("<hr>", unsafe_allow_html=True)

    # Row 3, Full Width: Minimum nights
    st.subheader("Ways to improve your occupancy rate 🚀")
    st.write("You can make your property even more attractive for your guests with these tips:")

    # Row 3 Layout
    row3_col1, row3_col2 = st.columns([5, 4])

    # Row 3, Column 1: Minimum nights
    with row3_col1:
        # Add a horizontal line at the top of Column 1
        st.markdown("<hr style='margin-top:0; margin-bottom:0;'>", unsafe_allow_html=True)

        amenities_col1 = [
            "🧴 **Basic items (bed linen, basic cooking essentials & shampoo):** 7.10%",
            "🍲 **Microwave:** 1.50%",
            "💨 **Hairdryer:** 3.90%",
            "🧺 **Iron:** 3.70%",
            "☕️ **Coffee maker:** 1.00%",
        ]
        for idx, amenity in enumerate(amenities_col1):
            if idx > 0:
                st.markdown("<hr style='margin-top:0; margin-bottom:0;'>",
                            unsafe_allow_html=True)  # Add a line before each item
            st.write(amenity)

        # Add a vertical line in Column 1
        st.markdown("<hr style='margin-top:0; margin-bottom:0; border-left: 1px solid #ddd;'>", unsafe_allow_html=True)

    # Row 3, Column 2: Minimum nights
    with row3_col2:
        # Add a horizontal line at the top of Column 2
        st.markdown("<hr style='margin-top:0; margin-bottom:0;'>", unsafe_allow_html=True)

        amenities_col2 = [
            "👨‍👩‍👧‍👦 **Family-friendly listings:** 2.90%",
            "🤳 **Self check-out:** 4.60%",
            "🍽️ **Dishes and silverware:** 2.10%",
            "🐶 **Allowing pets to stay:** 9.70%",
            "👮🏼‍ **Presence of a doorman:** 6.20%"
        ]
        for idx, amenity in enumerate(amenities_col2):
            if idx > 0:
                st.markdown("<hr style='margin-top:0; margin-bottom:0;'>",
                            unsafe_allow_html=True)  # Add a line before each item
            st.write(amenity)

        # Add a vertical line in Column 2
        st.markdown("<hr style='margin-top:0; margin-bottom:0; border-left: 1px solid #ddd;'>", unsafe_allow_html=True)
