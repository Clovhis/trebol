# Trebol

Aplicacion de escritorio para consultar resultados de Loto Plus y Quiniela.

La interfaz ahora utiliza `ttkbootstrap` para un estilo moderno y
animaciones de hover en los botones.

Se genera un archivo `trebol.log` con mensajes de depuración para facilitar
el troubleshooting de la aplicación.

## Ejecucion

Instalar dependencias:
```
pip install -r requirements.txt
```

Para correr la aplicacion:
```
python trebol.py
```
El archivo `trebol.log` se actualizará con información de la ejecución.
Si `pystray` está instalado, la aplicación mostrará un ícono en el área de
notificación para permitir minimizar y restaurar la ventana.

La página de resultados utiliza Cloudflare, por lo que el programa
descarga las versiones en texto mediante `https://r.jina.ai/` para poder
extraer la información.


## Crear ejecutable

Para compilar en Windows usando PyInstaller:
```
pyinstaller --onefile --windowed trebol.py
```
