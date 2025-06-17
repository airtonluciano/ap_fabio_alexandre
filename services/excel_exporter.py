import pandas as pd

def export_to_excel(df, path):
    try:
        df.to_excel(path, index=False)
    except Exception as e:
        print(f"Erro ao exportar Excel: {str(e)}")
