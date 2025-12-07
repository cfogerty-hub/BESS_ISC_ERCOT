import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import geopandas as gpd
import folium
import json, requests
from urllib.request import urlopen
import streamlit as st
import sys
from io import StringIO
from streamlit_folium import st_folium

st.set_page_config(page_title="Reference Price for Batteries in ERCOT",layout='wide')
st.title("Reference Price for Batteries in ERCOT")
st.write("This tool calculates uses historical settlement prices from ERCOT Hub Zones to calculate the revenues that a battery of a specified capacity and duration would be expected to make from arbitrage and ancillary services. These Reference Prices would then serve as a hypothetical price used to calculate an Index Storage Credit (ISCs). ISCs, inspired by the NYSERDA Bulk Energy Storage Program, are intended to cover the gap between Reference Prices and Strike Prices bid in by battery owners to incentivize development. See https://www.nyserda.ny.gov/All-Programs/Energy-Storage-Program/Developers-and-Contractors/Bulk-Storage-Incentives for more details on this program.")
st.write("Methodology: Using hub zone DAM settlement prices (https://www.ercot.com/mp/data-products/data-product-details?id=NP4-180-ER) for energy and capacity from 2022 to 2024, this tool calculates daily arbitrage revenues expected for batteries less than 8-hours in duration (spread between the highest and lowest 0 - 8 hours in a day based on duration). For batteries with duration between 8 and 12 hours, the tool calculates the weekly arbitrage revenues expected (spread between the highest and lowest 8 - 12 hours during the week based on duration). Ancillary service revenues are assumed to be the average DAM capacity prices (https://www.ercot.com/mp/data-products/data-product-details?id=NP4-181-ER) for an entire month across all revenue streams (NON-SPIN, REG-DOWN, REG-UP, RRS, ECRS). These assumptions are not sophisticated by design to set a baseline expected operational strategy for batteries.")
st.write("The strike prices are estimated as the cost of new entry to pay back the capital cost of a battery over 15 years based on the NREL 2024 estimated battery system cost in 2024 as a function of duration: y = 240.8x + 379.16 (https://docs.nrel.gov/docs/fy25osti/93281.pdf), where x is the duration and y is the capital cost in $/kW.")
duration = st.slider('Select a battery duration (hours):',0,12,4,1)
capacity = st.slider('Select a capacity (MW): ',0,1000,100,10)

hou_hub_counties = ['Montgomery','Waller','Harris','Fort Bend','Brazoria','Galveston','Chambers']

north_hub_counties = [
    'Montague','Cooke','Grayson','Fannin','Lamar','Red River',
    'Jack','Wise','Denton','Collin','Hunt','Hopkins','Delta','Franklin','Titus',
    'Stephens','Palo Pinto','Parker','Tarrant','Dallas','Rockwall','Rains','Wood',
    'Eastland','Erath','Hood','Somervell','Johnson','Ellis','Kaufman','Van Zandt','Smith',
    'Brown','Comanche','Bosque','Hill','Navarro','Henderson','Smith','Rusk',
    'San Saba', 'Mills','Hamilton','McLennan','Limestone','Freestone','Anderson','Cherokee',
    'Nacogdoches','San Augustine','Angelina','Houston','Grimes','Madison','Brazos',
    'Lampasas','Bell','Coryell','Falls','Robertson','Leon']

pan_hub_counties = [
    "Dallam", "Hartley", "Oldham", "Deaf Smith", "Parmer", "Bailey", "Cochran",
    "Hockley", "Sherman", "Hansford", "Ochiltree", "Lipscomb", "Roberts",
    "Hemphill", "Wheeler", "Gray", "Carson", "Hutchinson", "Moore", "Potter",
    "Armstrong", "Randall", "Donley", "Collingsworth", "Briscoe", "Castro",
    "Swisher", "Floyd", "Motley", "Childress", "Hall", "Hale", "Lamb",
    "Lubbock", "Crosby", "Dickens"
]

south_hub_counties = [
    "Maverick", "Zavala", "Frio", "Atascosa", "Karnes", "DeWitt", "Lavaca",
    "Gonzales",'Milam', "Guadalupe",'Lee', "Comal", "Kendall", "Bandera", "Medina", "Bexar",
    "Wilson",'Austin','Kerr','Wharton', "Goliad", 'Bastrop',"Victoria", "Calhoun", "Refugio", "Aransas",
    "San Patricio", 'Gillespie','Jackson','Caldwell',"Bee",'Llano', 'Hays','Travis','Burnet',"Live Oak", "McMullen", "La Salle", "Dimmit", "Webb",
    "Duval",'Fayette', "McCulloch", "Jim Wells",'Colorado','Blanco', "Nueces", "Kleberg", "Kenedy", "Brooks", "Starr",
    "Hidalgo",'Williamson','Washington','Burleson',"Willacy", "Cameron", "Zapata", "Jim Hogg", "Matagorda", "Mason"
]

west_hub_counties = [
    "El Paso",'Wichita', "Cottle",'Hardeman','Wilbarger','Young',"Hudspeth", "Culberson", "Reeves", "Loving", "Winkler", "Ward",
    "Crane", "Upton", "Reagan","Knox",'King', "Irion", "Jeff Davis", "Pecos", "Terrell",
    "Crockett","Archer", "Schleicher", "Sutton", "Kimble", "Menard", "Presidio",
    "Brewster", "Val Verde", "Edwards", "Real", "Kinney", "Uvalde", "Andrews",
    "Martin", "Howard", "Mitchell", "Nolan", "Taylor", "Callahan",
    "Baylor",'Tom Green',"Coleman", "Runnels", "Concho",
    "Midland", "Glasscock", "Sterling", "Coke", "Ector", "Gaines",
    "Dawson", "Borden", "Scurry", "Fisher", "Jones", "Shackelford", "Yoakum",
    "Terry",'Foard','Clay', "Lynn", "Garza", "Kent", "Stonewall", "Haskell", "Throckmorton",
]

## Locate non-ercot counties: https://www.ercot.com/news/mediakit/maps

non_ercot_counties = ['Dallam','Sherman','Hansford','Ochiltree','Lipscomb','Moore','Hartley','Hutchinson','Hemphill','Bailey','Lamb','Cochran','Hockley',
                      'Yoakum','Terry','Gaines','El Paso','Hudspeth','Bowie','Morris','Cass','Camp','Upshur','Marion','Harrison','Gregg','Panola','Shelby',
                      'San Augustine','Sabine','Newston','Jasper','Tyler','Polk','Trinity','San Jacinto','Liberty','Hardin','Orange','Jefferson']

## import TX counties shapefile

my_universal_path = Path("US_COUNTY_SHPFILE/US_county_cont.shp")

# read in a shapefile of US lower 48 counties, MUST SELECT the .shp!
us_county = gpd.read_file(my_universal_path)

us_county.head()

# plotting maps: https://geopandas.org/en/stable/docs/user_guide/mapping.html
us_county.plot()

# plot just the boundaries
us_county.boundary.plot(color="black")

# get the limits of the gdf
us_county.total_bounds

# get the coordinate reference system (CRS)
us_county.crs

# can aggregate geometry on a column: https://geopandas.org/en/stable/docs/user_guide/aggregation_with_dissolve.html
us_states = us_county.dissolve(
    by="STATE_NAME", aggfunc="sum"
)  # aggfunc: first (default), last, min, max, etc. BE CAREFULL!! Some columns don't make sense to sum, like names


# you can make a df from a gdf
us_df = pd.DataFrame(us_states)

## downselect to TX counties
list(us_county)

tx_county = us_county[us_county["STATE_NAME"] == "Texas"]

tx_county.plot()

tx_county.boundary.plot()

tx = tx_county.dissolve(by="STATE_NAME", aggfunc="sum")

ercot_zones = tx_county[tx_county['NAME'].isin(hou_hub_counties + north_hub_counties + pan_hub_counties + south_hub_counties + west_hub_counties)]

non_ercot_zones = tx_county[tx_county['NAME'].isin(non_ercot_counties)]

ercot_zones['hub zone'] = np.nan
ercot_zones.loc[ercot_zones['NAME'].isin(hou_hub_counties), 'hub zone'] = 'HOU'
ercot_zones.loc[ercot_zones['NAME'].isin(north_hub_counties), 'hub zone'] = 'NORTH'
ercot_zones.loc[ercot_zones['NAME'].isin(pan_hub_counties), 'hub zone'] = 'PAN'
ercot_zones.loc[ercot_zones['NAME'].isin(south_hub_counties), 'hub zone'] = 'SOUTH'
ercot_zones.loc[ercot_zones['NAME'].isin(west_hub_counties), 'hub zone'] = 'WEST'

hub_polygons = ercot_zones.dissolve(by='hub zone',aggfunc='sum')

hub_polygons = gpd.overlay(hub_polygons,non_ercot_zones,how='difference')

hub_polygons.index = ['HOU','NORTH','PAN','SOUTH','WEST']

fig, ax = plt.subplots(figsize=(8, 8))
hub_polygons.plot(column=hub_polygons.index, legend=True, ax=ax)
ax.set_title("ERCOT Hub Zones", fontsize=16)
st.pyplot(fig)

def RP_tables(duration, capacity):

    DATA_DIR = Path('ercot_data')

    capital_cost = 240.8 * duration + 379.16

    total_cost = capital_cost * 1000 * capacity

    annual_revenues_needed = total_cost/15

    annual_revenues_needed_per_mw = annual_revenues_needed/capacity

    if duration < 8:
        strike_price = (annual_revenues_needed_per_mw)/(365*duration)
    else:
        strike_price = (annual_revenues_needed_per_mw)/(52*duration)

    ## First, extract the hub prices to calculate the REAP.

    months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

    dam_hub_2022 = []
    dam_hub_2023 = []
    dam_hub_2024 = []

    for month in months:
        dam_hub_2022.append(pd.read_excel(DATA_DIR/'DAM_Hub_Prices_2022.xlsx',sheet_name=month))
        dam_hub_2023.append(pd.read_excel(DATA_DIR/'DAM_Hub_Prices_2023.xlsx',sheet_name=month))
        dam_hub_2024.append(pd.read_excel(DATA_DIR/'DAM_Hub_Prices_2024.xlsx',sheet_name=month))

    ## 2022 split out by hub zone.

    dam_hub_2022_houston = []
    dam_hub_2022_north = []
    dam_hub_2022_pan = []
    dam_hub_2022_south = []
    dam_hub_2022_west = []

    for i in range(0,12):
        dam = dam_hub_2022[i]
        dam_hub_2022_houston.append(dam[dam['Settlement Point'].isin(['HB_HOUSTON'])])
        dam_hub_2022_north.append(dam[dam['Settlement Point'].isin(['HB_NORTH'])])
        dam_hub_2022_pan.append(dam[dam['Settlement Point'].isin(['HB_PAN'])]) 
        dam_hub_2022_south.append(dam[dam['Settlement Point'].isin(['HB_SOUTH'])])
        dam_hub_2022_west.append(dam[dam['Settlement Point'].isin(['HB_WEST'])])

    dam_hub_2022_houston = pd.concat(dam_hub_2022_houston).set_index('Delivery Date')
    dam_hub_2022_north = pd.concat(dam_hub_2022_north).set_index('Delivery Date')
    dam_hub_2022_pan = pd.concat(dam_hub_2022_pan).set_index('Delivery Date')
    dam_hub_2022_south = pd.concat(dam_hub_2022_south).set_index('Delivery Date')
    dam_hub_2022_west = pd.concat(dam_hub_2022_west).set_index('Delivery Date')

    dam_hub_2022_houston.index = pd.to_datetime(dam_hub_2022_houston.index)
    dam_hub_2022_north.index = pd.to_datetime(dam_hub_2022_north.index)
    dam_hub_2022_pan.index = pd.to_datetime(dam_hub_2022_pan.index)
    dam_hub_2022_south.index = pd.to_datetime(dam_hub_2022_south.index)
    dam_hub_2022_west.index = pd.to_datetime(dam_hub_2022_west.index)

    ## 2023 split out by hub zone.

    dam_hub_2023_houston = []
    dam_hub_2023_north = []
    dam_hub_2023_pan = []
    dam_hub_2023_south = []
    dam_hub_2023_west = []

    for i in range(0,12):
        dam = dam_hub_2023[i]
        dam_hub_2023_houston.append(dam[dam['Settlement Point'].isin(['HB_HOUSTON'])])
        dam_hub_2023_north.append(dam[dam['Settlement Point'].isin(['HB_NORTH'])])
        dam_hub_2023_pan.append(dam[dam['Settlement Point'].isin(['HB_PAN'])]) 
        dam_hub_2023_south.append(dam[dam['Settlement Point'].isin(['HB_SOUTH'])])
        dam_hub_2023_west.append(dam[dam['Settlement Point'].isin(['HB_WEST'])])

    dam_hub_2023_houston = pd.concat(dam_hub_2023_houston).set_index('Delivery Date')
    dam_hub_2023_north = pd.concat(dam_hub_2023_north).set_index('Delivery Date')
    dam_hub_2023_pan = pd.concat(dam_hub_2023_pan).set_index('Delivery Date')
    dam_hub_2023_south = pd.concat(dam_hub_2023_south).set_index('Delivery Date')
    dam_hub_2023_west = pd.concat(dam_hub_2023_west).set_index('Delivery Date')

    dam_hub_2023_houston.index = pd.to_datetime(dam_hub_2023_houston.index)
    dam_hub_2023_north.index = pd.to_datetime(dam_hub_2023_north.index)
    dam_hub_2023_pan.index = pd.to_datetime(dam_hub_2023_pan.index)
    dam_hub_2023_south.index = pd.to_datetime(dam_hub_2023_south.index)
    dam_hub_2023_west.index = pd.to_datetime(dam_hub_2023_west.index)

    ## 2024 split out by hub zone.

    dam_hub_2024_houston = []
    dam_hub_2024_north = []
    dam_hub_2024_pan = []
    dam_hub_2024_south = []
    dam_hub_2024_west = []

    for i in range(0,12):
        dam = dam_hub_2024[i]
        dam_hub_2024_houston.append(dam[dam['Settlement Point'].isin(['HB_HOUSTON'])])
        dam_hub_2024_north.append(dam[dam['Settlement Point'].isin(['HB_NORTH'])])
        dam_hub_2024_pan.append(dam[dam['Settlement Point'].isin(['HB_PAN'])]) 
        dam_hub_2024_south.append(dam[dam['Settlement Point'].isin(['HB_SOUTH'])])
        dam_hub_2024_west.append(dam[dam['Settlement Point'].isin(['HB_WEST'])])

    dam_hub_2024_houston = pd.concat(dam_hub_2024_houston).set_index('Delivery Date')
    dam_hub_2024_north = pd.concat(dam_hub_2024_north).set_index('Delivery Date')
    dam_hub_2024_pan = pd.concat(dam_hub_2024_pan).set_index('Delivery Date')
    dam_hub_2024_south = pd.concat(dam_hub_2024_south).set_index('Delivery Date')
    dam_hub_2024_west = pd.concat(dam_hub_2024_west).set_index('Delivery Date')

    dam_hub_2024_houston.index = pd.to_datetime(dam_hub_2024_houston.index)
    dam_hub_2024_north.index = pd.to_datetime(dam_hub_2024_north.index)
    dam_hub_2024_pan.index = pd.to_datetime(dam_hub_2024_pan.index)
    dam_hub_2024_south.index = pd.to_datetime(dam_hub_2024_south.index)
    dam_hub_2024_west.index = pd.to_datetime(dam_hub_2024_west.index)

    ## define a function that collapses each spreadsheet into the highest and lowest hours

    def REAP(df, duration):
        monthly_reap = []
        for month in range(1,13):
            df_month = df['Settlement Point Price'][df.index.month == month]
            reap_list = []
            if duration < 8:
                for day in df_month.index.day.unique():
                    df_day = pd.DataFrame(df_month[df_month.index.day == day])
                    df_day = df_day.sort_values(by='Settlement Point Price',ascending=False)
                    df_high = df_day.iloc[0:duration]
                    df_low = df_day.iloc[-duration:]
                    df_low = df_low.sort_values(by='Settlement Point Price',ascending=True)
                    df_merged = pd.DataFrame({'high':df_high['Settlement Point Price'].values,'low':df_low['Settlement Point Price'].values})
                    df_merged['arbitrage'] = df_merged['high'] - df_merged['low']
                    daily_reap = np.mean(df_merged['arbitrage'])
                    reap_list.append(daily_reap)
            else:
                for week in df_month.index.isocalendar().week.unique():
                    df_week = pd.DataFrame(df_month[df_month.index.isocalendar().week == week])
                    df_week = df_week.sort_values(by='Settlement Point Price',ascending=False)
                    df_high = df_week.iloc[0:duration]
                    df_low = df_week.iloc[-duration:]
                    df_low = df_low.sort_values(by='Settlement Point Price',ascending=True)
                    df_merged = pd.DataFrame({'high':df_high['Settlement Point Price'].values,'low':df_low['Settlement Point Price'].values})
                    df_merged['arbitrage'] = df_merged['high'] - df_merged['low']
                    weekly_reap = np.mean(df_merged['arbitrage'])
                    reap_list.append(weekly_reap)
            reap_array = np.array(reap_list)
            avg_reap = np.mean(reap_array)
            monthly_reap.append(avg_reap)
        return monthly_reap

    reap_2022_houston = REAP(dam_hub_2022_houston,duration)
    reap_2022_north = REAP(dam_hub_2022_north,duration)
    reap_2022_pan = REAP(dam_hub_2022_pan,duration)
    reap_2022_south = REAP(dam_hub_2022_south,duration)
    reap_2022_west = REAP(dam_hub_2022_west,duration)

    reap_2023_houston = REAP(dam_hub_2023_houston,duration)
    reap_2023_north = REAP(dam_hub_2023_north,duration)
    reap_2023_pan = REAP(dam_hub_2023_pan,duration)
    reap_2023_south = REAP(dam_hub_2023_south,duration)
    reap_2023_west = REAP(dam_hub_2023_west,duration)

    reap_2024_houston = REAP(dam_hub_2024_houston,duration)
    reap_2024_north = REAP(dam_hub_2024_north,duration)
    reap_2024_pan = REAP(dam_hub_2024_pan,duration)
    reap_2024_south = REAP(dam_hub_2024_south,duration)
    reap_2024_west = REAP(dam_hub_2024_west,duration)

    ## extract capacity prices for the Reference Cap Prices

    dam_cap_2022 = pd.read_csv(DATA_DIR/'DAM_CapPrices2022.csv').set_index('Delivery Date')
    dam_cap_2023 = pd.read_csv(DATA_DIR/'DAM_CapPrices2023.csv').set_index('Delivery Date')
    dam_cap_2024 = pd.read_csv(DATA_DIR/'DAM_CapPrices2024.csv').set_index('Delivery Date')

    dam_cap_2022.index = pd.to_datetime(dam_cap_2022.index)
    dam_cap_2023.index = pd.to_datetime(dam_cap_2023.index)
    dam_cap_2024.index = pd.to_datetime(dam_cap_2024.index)

    def RCP(df):
        monthly_rcp = []
        for month in df.index.month.unique():
            df_month = pd.DataFrame(df[df.index.month==month])
            df_month['avg price'] = df_month[['REGDN','REGUP ','RRS','NSPIN']].mean(axis=1)
            monthly_avg_rcp = np.mean(df_month['avg price'])
            monthly_rcp.append(monthly_avg_rcp)
        return monthly_rcp

    rcp_2022 = RCP(dam_cap_2022)
    rcp_2023 = RCP(dam_cap_2023)
    rcp_2024 = RCP(dam_cap_2024)

    ## 2023

    RP_df_2022 = pd.DataFrame({'Reference Capacity Price':rcp_2022,
                            'Houston Hub Zone REAP':reap_2022_houston,
                            'North Hub Zone REAP':reap_2022_north,
                            'Panhandle Hub Zone REAP':reap_2022_pan,
                            'South Hub Zone REAP':reap_2022_south,
                            'West Hub Zone REAP':reap_2022_west})

    RP_df_2022.index = months

    RP_df_2022['Houston Reference Price'] = RP_df_2022[['Reference Capacity Price','Houston Hub Zone REAP']].sum(axis=1)
    RP_df_2022['North Reference Price'] = RP_df_2022[['Reference Capacity Price','North Hub Zone REAP']].sum(axis=1)
    RP_df_2022['Panhandle Reference Price'] = RP_df_2022[['Reference Capacity Price','Panhandle Hub Zone REAP']].sum(axis=1)
    RP_df_2022['South Reference Price'] = RP_df_2022[['Reference Capacity Price','South Hub Zone REAP']].sum(axis=1)
    RP_df_2022['West Reference Price'] = RP_df_2022[['Reference Capacity Price','West Hub Zone REAP']].sum(axis=1)

    RP_df_2022 = RP_df_2022.drop(columns=['Reference Capacity Price','Houston Hub Zone REAP','North Hub Zone REAP','Panhandle Hub Zone REAP','South Hub Zone REAP','West Hub Zone REAP'])

        ## 2023

    RP_df_2023 = pd.DataFrame({'Reference Capacity Price':rcp_2023,
                                'Houston Hub Zone REAP':reap_2023_houston,
                                'North Hub Zone REAP':reap_2023_north,
                                'Panhandle Hub Zone REAP':reap_2023_pan,
                                'South Hub Zone REAP':reap_2023_south,
                                'West Hub Zone REAP':reap_2023_west})

    RP_df_2023.index = months

    RP_df_2023['Houston Reference Price'] = RP_df_2023[['Reference Capacity Price','Houston Hub Zone REAP']].sum(axis=1)
    RP_df_2023['North Reference Price'] = RP_df_2023[['Reference Capacity Price','North Hub Zone REAP']].sum(axis=1)
    RP_df_2023['Panhandle Reference Price'] = RP_df_2023[['Reference Capacity Price','Panhandle Hub Zone REAP']].sum(axis=1)
    RP_df_2023['South Reference Price'] = RP_df_2023[['Reference Capacity Price','South Hub Zone REAP']].sum(axis=1)
    RP_df_2023['West Reference Price'] = RP_df_2023[['Reference Capacity Price','West Hub Zone REAP']].sum(axis=1)

    RP_df_2023 = RP_df_2023.drop(columns=['Reference Capacity Price','Houston Hub Zone REAP','North Hub Zone REAP','Panhandle Hub Zone REAP','South Hub Zone REAP','West Hub Zone REAP'])

        ## 2024

    RP_df_2024 = pd.DataFrame({'Reference Capacity Price':rcp_2024,
                                'Houston Hub Zone REAP':reap_2024_houston,
                                'North Hub Zone REAP':reap_2024_north,
                                'Panhandle Hub Zone REAP':reap_2024_pan,
                                'South Hub Zone REAP':reap_2024_south,
                                'West Hub Zone REAP':reap_2024_west})

    RP_df_2024.index = months

    RP_df_2024['Houston Reference Price'] = RP_df_2024[['Reference Capacity Price','Houston Hub Zone REAP']].sum(axis=1)
    RP_df_2024['North Reference Price'] = RP_df_2024[['Reference Capacity Price','North Hub Zone REAP']].sum(axis=1)
    RP_df_2024['Panhandle Reference Price'] = RP_df_2024[['Reference Capacity Price','Panhandle Hub Zone REAP']].sum(axis=1)
    RP_df_2024['South Reference Price'] = RP_df_2024[['Reference Capacity Price','South Hub Zone REAP']].sum(axis=1)
    RP_df_2024['West Reference Price'] = RP_df_2024[['Reference Capacity Price','West Hub Zone REAP']].sum(axis=1)

    RP_df_2024 = RP_df_2024.drop(columns=['Reference Capacity Price','Houston Hub Zone REAP','North Hub Zone REAP','Panhandle Hub Zone REAP','South Hub Zone REAP','West Hub Zone REAP'])

        ## subplots 

    fig, ax = plt.subplots(3,1,figsize=(15,10))
    ax[0].plot(RP_df_2022)
    ax[0].set_title(f'2022 Reference Prices by Hub Zone for {duration}-hr batteries')
    ax[0].set_ylabel('$/MWh')
    ax[0].legend(RP_df_2022.columns,loc='upper right')
    ax[1].plot(RP_df_2023)
    ax[1].set_title(f'2023 Reference Prices by Hub Zone for {duration}-hr batteries')
    ax[1].set_ylabel('$/MWh')
    ax[2].plot(RP_df_2024)
    ax[2].set_title(f'2024 Reference Prices by Hub Zone for {duration}-hr batteries')
    ax[2].set_ylabel('$/MWh')
    plt.tight_layout()
    fig.subplots_adjust(hspace=0.4)

    ref_prices = fig

        ## bar plots. Claude assisted with formatting.

    fig, ax = plt.subplots(3,1,figsize=(15,10))
    RP_df_2022.plot(kind='bar', figsize=(12, 6),ax=ax[0],legend=False)
    ax[0].set_ylabel('Reference Price ($/MWh)')
    ax[0].set_title(f'2022 Prices by Hub Zone Across Months {duration}-hr Batteries')
    ax[0].set_ylim(0,1000)
    RP_df_2023.plot(kind='bar', figsize=(12, 6),ax=ax[1],legend=False)
    ax[1].set_ylabel('Reference Price ($/MWh)')
    ax[1].set_title(f'2023 Prices by Hub Zone Across Months{duration}-hr Batteries')
    ax[1].set_ylim(0,1000)
    RP_df_2024.plot(kind='bar', figsize=(12, 6),ax=ax[2],legend=False)
    ax[2].set_xlabel('Month')
    ax[2].set_ylabel('Reference Price ($/MWh)')
    ax[2].set_title(f'2024 Prices by Hub Zone Across Months {duration}-hr Batteries')
    ax[2].set_ylim(0,1000)
    plt.tight_layout()

    handles, labels = ax[0].get_legend_handles_labels()
    fig.legend(handles, labels, 
                title='Hub Zones',
                loc='upper right',
                bbox_to_anchor=(0.98, 0.98),
                framealpha=0.7)  # 0.7 = 70% opacity (0=transparent, 1=opaque)

        ## August 2023 is dominant. Perhaps we should remove this outlier?

    avg_hou_aug = ((RP_df_2022['Houston Reference Price'][RP_df_2022.index == 'Aug'].iloc[0]) + (RP_df_2024['Houston Reference Price'][RP_df_2024.index == 'Aug'].iloc[0]))/2
    avg_north_aug = ((RP_df_2022['North Reference Price'][RP_df_2022.index == 'Aug'].iloc[0]) + (RP_df_2024['North Reference Price'][RP_df_2024.index == 'Aug'].iloc[0]))/2
    avg_pan_aug = ((RP_df_2022['Panhandle Reference Price'][RP_df_2022.index == 'Aug'].iloc[0]) + (RP_df_2024['Panhandle Reference Price'][RP_df_2024.index == 'Aug'].iloc[0]))/2
    avg_south_aug = ((RP_df_2022['South Reference Price'][RP_df_2022.index == 'Aug'].iloc[0]) + (RP_df_2024['South Reference Price'][RP_df_2024.index == 'Aug'].iloc[0]))/2
    avg_west_aug = ((RP_df_2022['West Reference Price'][RP_df_2022.index == 'Aug'].iloc[0]) + (RP_df_2024['West Reference Price'][RP_df_2024.index == 'Aug'].iloc[0]))/2

    RP_df_2023_aug_adjusted = RP_df_2023.copy()
    RP_df_2023_aug_adjusted['Houston Reference Price'][RP_df_2023_aug_adjusted.index == 'Aug'] = avg_hou_aug
    RP_df_2023_aug_adjusted['North Reference Price'][RP_df_2023_aug_adjusted.index == 'Aug'] = avg_north_aug
    RP_df_2023_aug_adjusted['Panhandle Reference Price'][RP_df_2023_aug_adjusted.index == 'Aug'] = avg_pan_aug
    RP_df_2023_aug_adjusted['South Reference Price'][RP_df_2023_aug_adjusted.index == 'Aug'] = avg_south_aug
    RP_df_2023_aug_adjusted['West Reference Price'][RP_df_2023_aug_adjusted.index == 'Aug'] = avg_west_aug

    fig, ax = plt.subplots(3,1,figsize=(15,10))
    RP_df_2022.plot(kind='bar', figsize=(12, 6),ax=ax[0],legend=False)
    ax[0].set_ylabel('Reference Price ($/MWh)')
    ax[0].set_title(f'2022 Prices by Hub Zone Across Months {duration}-hr Batteries')
    ax[0].set_ylim(0,1000)
    RP_df_2023_aug_adjusted.plot(kind='bar', figsize=(12, 6),ax=ax[1],legend=False)
    ax[1].set_ylabel('Reference Price ($/MWh)')
    ax[1].set_title(f'2023 Prices by Hub Zone Across Months with August Adjusted {duration}-hr Batteries')
    ax[1].set_ylim(0,1000)
    RP_df_2024.plot(kind='bar', figsize=(12, 6),ax=ax[2],legend=False)
    ax[2].set_xlabel('Month')
    ax[2].set_ylabel('Reference Price ($/MWh)')
    ax[2].set_title(f'2024 Prices by Hub Zone Across Months {duration}-hr Batteries')
    ax[2].set_ylim(0,1000)
    plt.tight_layout()

    handles, labels = ax[0].get_legend_handles_labels()
    fig.legend(handles, labels, 
                title='Hub Zones',
                loc='upper right',
                bbox_to_anchor=(0.98, 0.98),
                framealpha=0.7)  # 0.7 = 70% opacity (0=transparent, 1=opaque)

    bar_ref_prices = fig

        ## Test year for reference prices

    RP_df_test_year = pd.DataFrame({'Houston Reference Price':np.mean([RP_df_2022['Houston Reference Price'],RP_df_2023_aug_adjusted['Houston Reference Price'],RP_df_2024['Houston Reference Price']],axis=0),
                                            'North Reference Price':np.mean([RP_df_2022['North Reference Price'],RP_df_2023_aug_adjusted['North Reference Price'],RP_df_2024['North Reference Price']],axis=0),
                                            'Panhandle Reference Price':np.mean([RP_df_2022['Panhandle Reference Price'],RP_df_2023_aug_adjusted['Panhandle Reference Price'],RP_df_2024['Panhandle Reference Price']],axis=0),
                                            'South Reference Price':np.mean([RP_df_2022['South Reference Price'],RP_df_2023_aug_adjusted['South Reference Price'],RP_df_2024['South Reference Price']],axis=0),
                                            'West Reference Price':np.mean([RP_df_2022['West Reference Price'],RP_df_2023_aug_adjusted['West Reference Price'],RP_df_2024['West Reference Price']],axis=0)})
    RP_df_test_year.index = months

    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    month_number = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    energy = capacity * duration
    Hou_rev_list = []
    North_rev_list = []
    Pan_rev_list = []
    South_rev_list = []
    West_rev_list = []
    Strike_rev_list = []

    if duration < 8:
        for i in month_number:
            i = i - 1
            Hou_revenue = (RP_df_test_year['Houston Reference Price'][i]) * energy * days_per_month[i]
            Hou_rev_list.append(Hou_revenue)
            North_revenue = (RP_df_test_year['North Reference Price'][i]) * energy * days_per_month[i]
            North_rev_list.append(North_revenue)
            Pan_revenue = (RP_df_test_year['Panhandle Reference Price'][i]) * energy * days_per_month[i]
            Pan_rev_list.append(Pan_revenue)
            South_revenue = (RP_df_test_year['South Reference Price'][i]) * energy * days_per_month[i]
            South_rev_list.append(South_revenue)
            West_revenue = (RP_df_test_year['West Reference Price'][i]) * energy * days_per_month[i]
            West_rev_list.append(West_revenue)
            Strike_revenue = strike_price * energy * days_per_month[i]
            Strike_rev_list.append(Strike_revenue)
    else:
        for i in month_number:
            weeks_per_month = 4.5
            i = i - 1
            Hou_revenue = (RP_df_test_year['Houston Reference Price'][i]) * energy * weeks_per_month
            Hou_rev_list.append(Hou_revenue)
            North_revenue = (RP_df_test_year['North Reference Price'][i]) * energy * weeks_per_month
            North_rev_list.append(North_revenue)
            Pan_revenue = (RP_df_test_year['Panhandle Reference Price'][i]) * energy * weeks_per_month
            Pan_rev_list.append(Pan_revenue)
            South_revenue = (RP_df_test_year['South Reference Price'][i]) * energy * weeks_per_month
            South_rev_list.append(South_revenue)
            West_revenue = (RP_df_test_year['West Reference Price'][i]) * energy * weeks_per_month
            West_rev_list.append(West_revenue)
            Strike_revenue = strike_price * energy * weeks_per_month
            Strike_rev_list.append(Strike_revenue)

    revenues_df = pd.DataFrame({'Houston Monthly Reference Revenue ($)':Hou_rev_list,'North Monthly Reference Revenue ($)':North_rev_list,
                                'Panhandle Monthly Reference Revenue ($)':Pan_rev_list,'South Monthly Reference Revenue ($)':South_rev_list,
                                'West Monthly Reference Revenue ($)':West_rev_list})
    
    revenues_df.index = months

    total_test_year_revenues = {'Houston Hub Zone':[revenues_df['Houston Monthly Reference Revenue ($)'].sum(),sum(Strike_rev_list),sum(Strike_rev_list)-revenues_df['Houston Monthly Reference Revenue ($)'].sum()],
                                'North Hub Zone':[revenues_df['North Monthly Reference Revenue ($)'].sum(),sum(Strike_rev_list),sum(Strike_rev_list)-revenues_df['North Monthly Reference Revenue ($)'].sum()],
                                'Panhandle Hub Zone':[revenues_df['Panhandle Monthly Reference Revenue ($)'].sum(),sum(Strike_rev_list),sum(Strike_rev_list)-revenues_df['Panhandle Monthly Reference Revenue ($)'].sum()],
                                'South Hub Zone':[revenues_df['South Monthly Reference Revenue ($)'].sum(),sum(Strike_rev_list),sum(Strike_rev_list)-revenues_df['South Monthly Reference Revenue ($)'].sum()],
                                'West Hub Zone':[revenues_df['West Monthly Reference Revenue ($)'].sum(),sum(Strike_rev_list),sum(Strike_rev_list)-revenues_df['West Monthly Reference Revenue ($)'].sum()]}
    
    total_revenues_df = pd.DataFrame(total_test_year_revenues)
    total_revenues_df.index = ['Annual Reference Revenues ($)','Annual Strike Price Revenues ($)','Index Storage Credits']

    hz_names = ['Houston','North','Panhandle','South','West']
    neg_hzs = []

    for i in range(len(total_revenues_df.columns)):
        if total_revenues_df.iloc[2][i]<0:
            hub_zone_negative = hz_names[i]
            neg_hzs.append(hub_zone_negative)
    
    max_hub_zone = total_revenues_df.iloc[0].idxmax()

    hub_zone_descending = total_revenues_df.iloc[2].sort_values(ascending=False).index.to_list()

    fig, ax = plt.subplots(figsize=(12, 6))
    RP_df_test_year.plot(kind='bar', figsize=(12, 6),ax=ax,legend=False)
    ax.set_ylabel('Reference Price ($/MWh)')        
    ax.set_title(f'Test Year (Average of 2022-2024) Prices by Hub Zone Across Months {duration}-hr Batteries')
    plt.tight_layout()
    ax.axhline(y=strike_price, color='red', linestyle='--', linewidth=1.5, label='Strike Price')

    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, 
                title='Hub Zones',
                loc='upper right',
                bbox_to_anchor=(0.98, 0.98),
                framealpha=0.7)  # 0.7 = 70% opacity (0=transparent, 1=opaque)

    test_year = fig

    ## reshape for mapping

    RP_df_test_year = RP_df_test_year.T

    df = RP_df_test_year
    ## df = df.rename(columns={'Unnamed: 0': 'Hub Zone'})
    ## df.set_index('Hub Zone', inplace=True)

    hou_hub_counties = ['Montgomery','Waller','Harris','Fort Bend','Brazoria','Galveston','Chambers']

    north_hub_counties = [
        'Montague','Cooke','Grayson','Fannin','Lamar','Red River',
        'Jack','Wise','Denton','Collin','Hunt','Hopkins','Delta','Franklin','Titus',
        'Stephens','Palo Pinto','Parker','Tarrant','Dallas','Rockwall','Rains','Wood',
        'Eastland','Erath','Hood','Somervell','Johnson','Ellis','Kaufman','Van Zandt','Smith',
        'Brown','Comanche','Bosque','Hill','Navarro','Henderson','Smith','Rusk',
        'San Saba', 'Mills','Hamilton','McLennan','Limestone','Freestone','Anderson','Cherokee',
        'Nacogdoches','San Augustine','Angelina','Houston','Grimes','Madison','Brazos',
        'Lampasas','Bell','Coryell','Falls','Robertson','Leon']

    pan_hub_counties = [
        "Dallam", "Hartley", "Oldham", "Deaf Smith", "Parmer", "Bailey", "Cochran",
        "Hockley", "Sherman", "Hansford", "Ochiltree", "Lipscomb", "Roberts",
        "Hemphill", "Wheeler", "Gray", "Carson", "Hutchinson", "Moore", "Potter",
        "Armstrong", "Randall", "Donley", "Collingsworth", "Briscoe", "Castro",
        "Swisher", "Floyd", "Motley", "Childress", "Hall", "Hale", "Lamb",
        "Lubbock", "Crosby", "Dickens"
    ]

    south_hub_counties = [
        "Maverick", "Zavala", "Frio", "Atascosa", "Karnes", "DeWitt", "Lavaca",
        "Gonzales",'Milam', "Guadalupe",'Lee', "Comal", "Kendall", "Bandera", "Medina", "Bexar",
        "Wilson",'Austin','Kerr','Wharton', "Goliad", 'Bastrop',"Victoria", "Calhoun", "Refugio", "Aransas",
        "San Patricio", 'Gillespie','Jackson','Caldwell',"Bee",'Llano', 'Hays','Travis','Burnet',"Live Oak", "McMullen", "La Salle", "Dimmit", "Webb",
        "Duval",'Fayette', "McCulloch", "Jim Wells",'Colorado','Blanco', "Nueces", "Kleberg", "Kenedy", "Brooks", "Starr",
        "Hidalgo",'Williamson','Washington','Burleson',"Willacy", "Cameron", "Zapata", "Jim Hogg", "Matagorda", "Mason"
    ]

    west_hub_counties = [
        "El Paso",'Wichita', "Cottle",'Hardeman','Wilbarger','Young',"Hudspeth", "Culberson", "Reeves", "Loving", "Winkler", "Ward",
        "Crane", "Upton", "Reagan","Knox",'King', "Irion", "Jeff Davis", "Pecos", "Terrell",
        "Crockett","Archer", "Schleicher", "Sutton", "Kimble", "Menard", "Presidio",
        "Brewster", "Val Verde", "Edwards", "Real", "Kinney", "Uvalde", "Andrews",
        "Martin", "Howard", "Mitchell", "Nolan", "Taylor", "Callahan",
        "Baylor",'Tom Green',"Coleman", "Runnels", "Concho",
        "Midland", "Glasscock", "Sterling", "Coke", "Ector", "Gaines",
        "Dawson", "Borden", "Scurry", "Fisher", "Jones", "Shackelford", "Yoakum",
        "Terry",'Foard','Clay', "Lynn", "Garza", "Kent", "Stonewall", "Haskell", "Throckmorton",
    ]

    ## Locate non-ercot counties: https://www.ercot.com/news/mediakit/maps

    non_ercot_counties = ['Dallam','Sherman','Hansford','Ochiltree','Lipscomb','Moore','Hartley','Hutchinson','Hemphill','Bailey','Lamb','Cochran','Hockley',
                        'Yoakum','Terry','Gaines','El Paso','Hudspeth','Bowie','Morris','Cass','Camp','Upshur','Marion','Harrison','Gregg','Panola','Shelby',
                        'San Augustine','Sabine','Newston','Jasper','Tyler','Polk','Trinity','San Jacinto','Liberty','Hardin','Orange','Jefferson']

    ## import TX counties shapefile

    my_universal_path = Path("US_COUNTY_SHPFILE/US_county_cont.shp")

    # read in a shapefile of US lower 48 counties, MUST SELECT the .shp!
    us_county = gpd.read_file(my_universal_path)

    us_county.head()

    # plotting maps: https://geopandas.org/en/stable/docs/user_guide/mapping.html
    ## us_county.plot()

    # plot just the boundaries
    ## us_county.boundary.plot(color="black")

    # get the limits of the gdf
    ## us_county.total_bounds

    # get the coordinate reference system (CRS)
    ## us_county.crs

    # can aggregate geometry on a column: https://geopandas.org/en/stable/docs/user_guide/aggregation_with_dissolve.html
    us_states = us_county.dissolve(
        by="STATE_NAME", aggfunc="sum"
    )  # aggfunc: first (default), last, min, max, etc. BE CAREFULL!! Some columns don't make sense to sum, like names


    # you can make a df from a gdf
    us_df = pd.DataFrame(us_states)

    ## downselect to TX counties
    list(us_county)

    tx_county = us_county[us_county["STATE_NAME"] == "Texas"]

    ## tx_county.plot()

    ## tx_county.boundary.plot()

    tx = tx_county.dissolve(by="STATE_NAME", aggfunc="sum")

    ercot_zones = tx_county[tx_county['NAME'].isin(hou_hub_counties + north_hub_counties + pan_hub_counties + south_hub_counties + west_hub_counties)]

    non_ercot_zones = tx_county[tx_county['NAME'].isin(non_ercot_counties)]

    ercot_zones['hub zone'] = np.nan
    ercot_zones.loc[ercot_zones['NAME'].isin(hou_hub_counties), 'hub zone'] = 'HOU'
    ercot_zones.loc[ercot_zones['NAME'].isin(north_hub_counties), 'hub zone'] = 'NORTH'
    ercot_zones.loc[ercot_zones['NAME'].isin(pan_hub_counties), 'hub zone'] = 'PAN'
    ercot_zones.loc[ercot_zones['NAME'].isin(south_hub_counties), 'hub zone'] = 'SOUTH'
    ercot_zones.loc[ercot_zones['NAME'].isin(west_hub_counties), 'hub zone'] = 'WEST'

    hub_polygons = ercot_zones.dissolve(by='hub zone',aggfunc='sum')

    hub_polygons = gpd.overlay(hub_polygons,non_ercot_zones,how='difference')

    hub_polygons.index = ['HOU','NORTH','PAN','SOUTH','WEST']

    fig, ax = plt.subplots(figsize=(8, 8))
    hub_polygons.plot(column=hub_polygons.index, legend=True, ax=ax)
    ax.set_title("ERCOT Hub Zones", fontsize=16)
    hubs_map = fig

    hub_polygons_df = pd.DataFrame(hub_polygons)
    df.index = hub_polygons_df.index
    hub_polygons_df = hub_polygons_df.merge(df, left_index=True, right_index=True)
    hub_polygons_df = hub_polygons_df.drop(columns=['OBJECTID','NAME','STATE_NAME','STATE_FIPS','CNTY_FIPS','FIPS','SQMI','Shape_Leng','Shape_Area'])
    hub_polygons_df = gpd.GeoDataFrame(hub_polygons_df)

    return ref_prices, bar_ref_prices, test_year, revenues_df, total_revenues_df, max_hub_zone, hub_zone_descending, neg_hzs, strike_price, hubs_map ## hub_polygons_df

if st.button('Run'):
    ref_prices, bar_ref_prices, test_year, revenues_df, total_revenues_df, max_hub_zone, hub_zone_descending, neg_hzs, strike_price, hubs_map = RP_tables(duration, capacity)

    st.pyplot(hubs_map)

    st.pyplot(ref_prices)

    st.write(f'August 2023 is an outlier. Below, August 2023 reference price is adjusted to equal the average of the 2022 and 2024 August RPs.')

    st.pyplot(bar_ref_prices)

    st.write(f'Below is the test year Reference Prices, calculated as the average of the 2022-2024 Reference Prices.')

    st.pyplot(test_year)

    st.dataframe(revenues_df)

    st.write(f'Below are the revenues for a {capacity} MW battery with a {duration}-hr duration.')
    
    st.write(f'For a {capacity} MW with a {duration}-hr duration, the estimated strike price (CONE) is ${strike_price}/MWh.')

    st.dataframe(total_revenues_df)

    st.write(f'The hub zone with the maximum reference revenues is: {max_hub_zone}')

    if len(neg_hzs) == 5:
        st.write(f'ERCOT generates sufficient revenues across all hub zones. No incentives are needed.')
    elif 0 < len(neg_hzs) < 5:
        st.write(f'The following hub zones have sufficient reference prices at this strike price. No Index Storage Credits are needed: {neg_hzs}. The rest need incentives.')
    else:
        st.write(f'All hub zones have Reference Revenues below Strike Price revenues. Incentives may be needed. Hub zones with estimated ISCs ranked from highest to lowest: {hub_zone_descending}')


    ## st.pyplot(hub_polygons_df)

    # Convert index to column if it's named (so all properties are accessible)

    ## gdf = hub_polygons_df.copy() 
    ## gdf['Hub Zone'] = gdf.index

    ## hub_zone_col = 'Hub Zone'

    # Compute map center
    ## center = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]

    # Convert to GeoJSON (all properties will be included)
    ## geojson_data = json.loads(gdf.to_json())

    # Extract columns for tooltip (those with 'Reference Price' in the name)
    ## months = [c for c in gdf.columns if c not in ['geometry', hub_zone_col]]

    ## tooltip_cols = [hub_zone_col] + months
    ## tooltip_aliases = ["Hub Zone"] + months

    # Create folium map
    ## m = folium.Map(location=center, zoom_start=7, tiles="OpenStreetMap")

    ## geojson = folium.GeoJson(
        ## geojson_data,
        ## name="ERCOT Hubs",
        ## style_function=lambda feature: {
            ## "color": "#3186cc",
            ## "weight": 1.5,
            ## "fillOpacity": 0.35,
        ## },
        ## tooltip=folium.features.GeoJsonTooltip(
            ## fields=tooltip_cols,
            ## aliases=tooltip_aliases,
            ## sticky=True,
        ## ),
    ## )
    ## geojson.add_to(m)

    # Render in Streamlit
    ## st_folium(m, width=800, height=700)