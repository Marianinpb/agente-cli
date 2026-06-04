import sys
from pathlib import Path

# Agregar el directorio raíz al path para las importaciones
sys.path.append(str(Path(__file__).parent))

from ui.app import IicoApp

def main():
    app = IicoApp()
    app.run()

if __name__ == "__main__":
    main()
