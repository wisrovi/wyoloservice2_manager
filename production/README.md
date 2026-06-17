# WDarwin Ops - Manager Production Deployment

Esta carpeta contiene los archivos necesarios para levantar el **Manager** y su **Cluster Control Center (UI)** en un entorno de producción, aislando el despliegue del código fuente de desarrollo.

## Diferencias con el entorno de Desarrollo
1. **No hay `--build`**: Usa directamente las imágenes precompiladas de Docker Hub (`wisrovi/train_service`).
2. **No hay volúmenes de código**: El código ya está inyectado dentro de las imágenes, lo que evita que cambios locales accidentales rompan el entorno productivo.
3. **Reinicio Constante**: Se usa `restart: always` para asegurar alta disponibilidad ante reinicios del servidor.

## Cómo desplegar
1. Revisa o modifica el archivo `control_host.env` con las IPs correctas.
2. Levanta los servicios descargando las imágenes de Docker Hub:

```bash
docker compose pull
docker compose up -d
```

3. Accede al Cluster Control Center en el puerto 80 de este servidor.
