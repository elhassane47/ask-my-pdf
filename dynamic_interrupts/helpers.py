import pandas as pd

def read_file_content(f):
    name = f.name.lower()
    data = f.read()  # Read once

    if name.endswith('.txt') or name.endswith('.csv'):
        # Decode bytes to string
        return data.decode('utf-8', errors='ignore')

    elif name.endswith('.xlsx'):
        # Use BytesIO to wrap the binary data
        excel_data = BytesIO(data)
        df = pd.read_excel(excel_data)
        return df.to_csv(index=False)

    else:
        # Unsupported file type or handle as plain text fallback
        try:
            return data.decode('utf-8', errors='ignore')
        except Exception:
            return ''