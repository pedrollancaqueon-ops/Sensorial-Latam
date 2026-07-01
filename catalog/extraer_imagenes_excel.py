import zipfile
import shutil
from pathlib import Path

def extraer_imagenes(excel_path: str, carpeta_salida: str = "imagenes_catalogo"):
    excel = Path(excel_path)
    salida = Path(carpeta_salida)
    salida.mkdir(exist_ok=True)

    with zipfile.ZipFile(excel, "r") as z:
        imagenes = [f for f in z.namelist() if f.startswith("xl/media/")]
        if not imagenes:
            print("No se encontraron imágenes en el archivo.")
            return

        for img_path in imagenes:
            nombre = Path(img_path).name
            destino = salida / f"{excel.stem}_{nombre}"
            with z.open(img_path) as src, open(destino, "wb") as dst:
                shutil.copyfileobj(src, dst)
            print(f"  Extraída: {destino}")

    print(f"\nTotal: {len(imagenes)} imágenes en '{salida}/'")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python extraer_imagenes_excel.py archivo.xlsx [carpeta_salida]")
        sys.exit(1)

    carpeta = sys.argv[2] if len(sys.argv) > 2 else "imagenes_catalogo"
    extraer_imagenes(sys.argv[1], carpeta)
