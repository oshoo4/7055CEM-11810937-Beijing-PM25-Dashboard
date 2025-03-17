from flask import Flask, render_template, request
import pandas as pd
import plotly.express as px
import plotly.io as pio
import json
import pymongo

app = Flask(__name__)

MONGO_URI = "mongodb+srv://beijingpmuser:Password123@beijingpm25-11810937-cl.7xrbhfd.mongodb.net/?retryWrites=true&w=majority&appName=beijingpm25-11810937-cluster"
DATABASE_NAME = "beijing_pm25"
COLLECTION_NAME = "beijing_data"

client = pymongo.MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

def load_data_from_mongodb():
    """Loads data from MongoDB."""
    try:
        cursor = collection.find({})
        data = pd.DataFrame(list(cursor))
        if '_id' in data.columns:
            data = data.drop('_id', axis=1)

        data['datetime'] = pd.to_datetime(data['datetime'])
        return data
    except Exception as e:
        print(f"Error loading data from MongoDB: {e}")
        return pd.DataFrame()

def insert_data_to_mongodb(filepath='data/processed_data.csv'):
    try:
        data = pd.read_csv(filepath)
        data['datetime'] = pd.to_datetime(data['datetime'])
        data_dict = data.to_dict(orient='records')

        if collection.count_documents({}) == 0:
            collection.insert_many(data_dict)
            print("Data inserted successfully!")
        else:
            print("Collection is not empty. Skipping insertion.")

    except Exception as e:
        print(f"Error inserting data: {e}")

def create_timeseries_plot(data, y_column, title, y_label):
    fig = px.line(data, x='datetime', y=y_column, title=title)
    fig.update_xaxes(title_text='Date and Time')
    fig.update_yaxes(title_text=y_label)
    return fig

def create_histogram(data, column, title, x_label, nbins=50, x_range=None):
    fig = px.histogram(data, x=column, title=title, nbins=nbins)
    fig.update_xaxes(title_text=x_label)
    fig.update_yaxes(title_text='Frequency')
    if x_range:
        fig.update_xaxes(range=x_range)
    return fig

def create_scatter_plot(data, x_column, y_column, title, x_label, y_label, x_range=None, y_range=None):
    fig = px.scatter(data, x=x_column, y=y_column, title=title,
                     hover_data=['datetime'])
    fig.update_xaxes(title_text=x_label)
    fig.update_yaxes(title_text=y_label)
    if x_range:
        fig.update_xaxes(range=x_range)
    if y_range:
        fig.update_yaxes(range=y_range)
    return fig

def create_heatmap_data(data, pm_column):
    data['month'] = data['datetime'].dt.month
    data['hour'] = data['datetime'].dt.hour
    heatmap_data = data.groupby(['month', 'hour'])[pm_column].mean().reset_index()
    heatmap_data = heatmap_data.pivot(index='month', columns='hour', values=pm_column)
    heatmap_data = heatmap_data.fillna(0).astype(float)
    return heatmap_data

def create_heatmap_plot(heatmap_data, title, x_label, y_label):
    fig = px.imshow(heatmap_data,
                    labels=dict(x=x_label, y=y_label, color="PM2.5"),
                    x=heatmap_data.columns,
                    y=heatmap_data.index,
                    color_continuous_scale="viridis",
                    origin='lower')

    fig.update_xaxes(side="top")
    fig.update_layout(title_text=title)
    return fig

@app.route('/', methods=['GET', 'POST'])
def index():
    data = load_data_from_mongodb()

    if data.empty:
        return "Error: Unable to load data from MongoDB.  Check your connection and data."

    pm_selection = request.form.get('pm_selection', 'PM_Average')

    if pm_selection not in data.columns:
        pm_selection = 'PM_Average'

    filtered_data = data[['datetime', pm_selection] + ['DEWP', 'HUMI', 'PRES', 'TEMP', 'Iws', 'precipitation']].copy()
    filtered_data.rename(columns={pm_selection:'PM_Selected'}, inplace=True)
    pm_plot = create_timeseries_plot(filtered_data, 'PM_Selected', f'{pm_selection} Levels Over Time', 'PM2.5 (ug/m³)')
    pm_plot_json = pio.to_json(pm_plot)

    pm_hist = create_histogram(filtered_data, 'PM_Selected', f'Distribution of {pm_selection} Levels', 'PM2.5 (ug/m³)', x_range=[0, data[pm_selection].max()])
    pm_hist_json = pio.to_json(pm_hist)

    scatter_plots = {}
    meteorological_vars = ['DEWP', 'HUMI', 'PRES', 'TEMP', 'Iws', 'precipitation']
    for var in meteorological_vars:
        x_min = filtered_data[var].min()
        x_max = filtered_data[var].max()
        scatter_plot = create_scatter_plot(
            filtered_data, var, 'PM_Selected', f'{pm_selection} vs. {var}', var, 'PM2.5 (ug/m³)',
            x_range=[x_min, x_max], y_range=[0, data[pm_selection].max()]
        )
        scatter_plots[var] = pio.to_json(scatter_plot)

    heatmap_data = create_heatmap_data(data.copy(), pm_selection)
    pm_heatmap = create_heatmap_plot(heatmap_data, f'{pm_selection} Levels by Hour and Month', 'Hour of Day', 'Month')
    pm_heatmap_json = pio.to_json(pm_heatmap)

    return render_template('index.html', pm_plot_json=pm_plot_json, pm_hist_json=pm_hist_json,
                           scatter_plots=scatter_plots, pm_heatmap_json=pm_heatmap_json,
                           pm_selection=pm_selection)

if __name__ == '__main__':
    app.run(debug=True)