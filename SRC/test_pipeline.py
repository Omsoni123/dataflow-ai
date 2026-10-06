from data_cleaning import process_data

file_path = "C:/Users/Om Soni/OneDrive/Desktop/Sales_analytical_api/Data/sales.csv"

data = process_data(file_path)

print("\nPipeline completed successfully!")
print(data.head())