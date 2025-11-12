# 🔒 Validación de Competencia en Curso

El sistema WebSocket ahora **valida que la competencia esté en curso** antes de aceptar registros de tiempos.

---

## 🎯 Reglas de Validación

### 1️⃣ **Al Conectar WebSocket**

✅ **Permitido**: Conectarse si la competencia está activa (`activa=True`)
❌ **Rechazado**: Conectarse si la competencia está inactiva (`activa=False`)

```javascript
// Si la competencia NO está activa, la conexión se cierra automáticamente
const ws = new WebSocket(`ws://127.0.0.1:8000/ws/juez/${juezId}/?token=${token}`);

ws.onclose = () => {
  console.log('❌ Conexión rechazada: competencia no activa');
};
```

### 2️⃣ **Al Registrar Tiempo**

✅ **Permitido**: Registrar si `competencia.en_curso = True`
❌ **Rechazado**: Registrar si `competencia.en_curso = False`

```javascript
// Si intentas registrar tiempo antes de iniciar la competencia:
ws.send(JSON.stringify({
  tipo: 'registrar_tiempo',
  equipo_id: 1,
  tiempo: 123456,
  // ...
}));

// Respuesta del servidor:
{
  tipo: 'error',
  mensaje: 'No se pueden registrar tiempos. La competencia no ha iniciado o ya finalizó.'
}
```

---

## 📡 Flujo Completo

### **Paso 1: Login y Conexión**

```javascript
// 1. Login
const response = await fetch('http://127.0.0.1:8000/api/login/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({username: 'juez1', password: 'password123'})
});

const data = await response.json();
console.log('Competencia:', data.juez.competencia);
// {
//   id: 1,
//   nombre: "Carrera 5K",
//   en_curso: false,  ← NO INICIADA
//   activa: true
// }

// 2. Conectar WebSocket
const ws = new WebSocket(
  `ws://127.0.0.1:8000/ws/juez/${data.juez.id}/?token=${data.access}`
);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log('📨 Mensaje:', msg);
};

// Recibes confirmación de conexión:
{
  tipo: 'conexion_establecida',
  mensaje: 'Conectado exitosamente',
  competencia: {
    id: 1,
    nombre: 'Carrera 5K',
    en_curso: false,  ← AÚN NO PUEDES REGISTRAR
    activa: true
  }
}
```

### **Paso 2: Esperar Inicio de Competencia**

```javascript
// El administrador inicia la competencia desde el panel admin
// Automáticamente recibes esta notificación:

{
  tipo: 'competencia_iniciada',
  mensaje: 'La competencia ha iniciado. Ya puedes registrar tiempos.',
  competencia: {
    id: 1,
    nombre: 'Carrera 5K',
    en_curso: true  ← AHORA SÍ PUEDES REGISTRAR
  }
}
```

### **Paso 3: Registrar Tiempos (Ahora Permitido)**

```javascript
// Ahora puedes enviar registros
ws.send(JSON.stringify({
  tipo: 'registrar_tiempo',
  equipo_id: 1,
  tiempo: 1234567,
  horas: 0,
  minutos: 20,
  segundos: 34,
  milisegundos: 567
}));

// Respuesta exitosa:
{
  tipo: 'tiempo_registrado',
  registro: {
    id_registro: "uuid-xxx",
    equipo_id: 1,
    equipo_nombre: "Equipo A",
    tiempo: 1234567,
    // ...
  }
}
```

### **Paso 4: Competencia Finalizada**

```javascript
// El administrador detiene la competencia
// Recibes esta notificación:

{
  tipo: 'competencia_detenida',
  mensaje: 'La competencia ha finalizado. No se pueden registrar más tiempos.',
  competencia: {
    id: 1,
    nombre: 'Carrera 5K',
    en_curso: false  ← YA NO PUEDES REGISTRAR
  }
}

// Si intentas registrar después de finalizada:
ws.send(JSON.stringify({
  tipo: 'registrar_tiempo',
  equipo_id: 2,
  // ...
}));

// Respuesta de error:
{
  tipo: 'error',
  mensaje: 'No se pueden registrar tiempos. La competencia no ha iniciado o ya finalizó.'
}
```

---

## 🛡️ Seguridad Implementada

| Validación | Ubicación | Descripción |
|------------|-----------|-------------|
| **Competencia activa** | `connect()` | Solo permite conectar si `competencia.activa = True` |
| **Competencia en curso** | `guardar_registro_tiempo()` | Solo permite registrar si `competencia.en_curso = True` |
| **Equipo asignado** | `guardar_registro_tiempo()` | Solo permite registrar equipos del juez autenticado |
| **Token válido** | `connect()` | Valida JWT antes de aceptar conexión |

---

## 🧪 Prueba Completa en Consola

```javascript
// Ejecuta este código en la consola del navegador

let miWS = null;
let competenciaEnCurso = false;

// 1. Login
fetch('http://127.0.0.1:8000/api/login/', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({username: 'roryflowers', password: 'teclado12'})
})
.then(r => r.json())
.then(data => {
  console.log('✅ Login exitoso');
  console.log('📊 Estado inicial:', data.juez.competencia);
  
  // 2. Conectar WebSocket
  miWS = new WebSocket(
    `ws://127.0.0.1:8000/ws/juez/${data.juez.id}/?token=${data.access}`
  );
  
  miWS.onopen = () => {
    console.log('🔌 WebSocket conectado');
  };
  
  miWS.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    console.log('📨 Mensaje recibido:', msg);
    
    // Actualizar estado
    if (msg.tipo === 'conexion_establecida') {
      competenciaEnCurso = msg.competencia.en_curso;
      console.log(`🏁 Competencia en curso: ${competenciaEnCurso}`);
    }
    
    if (msg.tipo === 'competencia_iniciada') {
      competenciaEnCurso = true;
      console.log('🟢 ¡COMPETENCIA INICIADA! Ahora puedes registrar tiempos.');
    }
    
    if (msg.tipo === 'competencia_detenida') {
      competenciaEnCurso = false;
      console.log('🔴 COMPETENCIA DETENIDA. No se aceptan más registros.');
    }
    
    if (msg.tipo === 'tiempo_registrado') {
      console.log('✅ Tiempo registrado exitosamente:', msg.registro);
    }
    
    if (msg.tipo === 'error') {
      console.error('❌ Error:', msg.mensaje);
    }
  };
  
  miWS.onerror = (error) => {
    console.error('❌ Error WebSocket:', error);
  };
  
  miWS.onclose = () => {
    console.log('🔌 WebSocket desconectado');
  };
});

// Función helper para registrar tiempo
function registrarTiempo(equipoId, tiempo = 1234567) {
  if (!miWS || miWS.readyState !== WebSocket.OPEN) {
    console.error('❌ WebSocket no conectado');
    return;
  }
  
  if (!competenciaEnCurso) {
    console.warn('⚠️ La competencia no está en curso. El servidor rechazará el registro.');
  }
  
  miWS.send(JSON.stringify({
    tipo: 'registrar_tiempo',
    equipo_id: equipoId,
    tiempo: tiempo,
    horas: 0,
    minutos: 20,
    segundos: 34,
    milisegundos: 567
  }));
  
  console.log(`📤 Registro enviado para equipo ${equipoId}`);
}

// Usar así:
// registrarTiempo(1);  // Intentar registrar equipo 1
```

---

## 📋 Checklist de Prueba

1. ✅ **Conectar antes de iniciar competencia**
   - Debe conectar exitosamente
   - Debe recibir `en_curso: false`

2. ✅ **Intentar registrar antes de iniciar**
   - Debe recibir error: "La competencia no ha iniciado"

3. ✅ **Iniciar competencia desde admin**
   - Debe recibir notificación `competencia_iniciada`

4. ✅ **Registrar durante competencia**
   - Debe registrar exitosamente
   - Debe recibir confirmación con datos del registro

5. ✅ **Detener competencia desde admin**
   - Debe recibir notificación `competencia_detenida`

6. ✅ **Intentar registrar después de detener**
   - Debe recibir error: "La competencia ya finalizó"

---

## 🎯 Resumen

| Estado Competencia | Conectar WS | Registrar Tiempo |
|-------------------|-------------|------------------|
| `activa=False` | ❌ Rechazado | ❌ N/A (no conecta) |
| `activa=True, en_curso=False` | ✅ Permitido | ❌ Rechazado |
| `activa=True, en_curso=True` | ✅ Permitido | ✅ Permitido |
| Competencia finalizada | ✅ Permitido* | ❌ Rechazado |

*Puede mantener conexión pero no registrar

---

## 💡 Para Aplicación Móvil

Tu app móvil debe:

1. **Conectar al WebSocket** después del login
2. **Escuchar eventos** `competencia_iniciada` y `competencia_detenida`
3. **Habilitar/deshabilitar botones** según el estado de `en_curso`
4. **Mostrar mensajes** al usuario cuando cambie el estado
5. **Validar localmente** antes de enviar (opcional, pero mejora UX)

```dart
// Ejemplo Flutter/Dart
void onWebSocketMessage(dynamic message) {
  switch (message['tipo']) {
    case 'competencia_iniciada':
      setState(() {
        competenciaEnCurso = true;
        mostrarNotificacion('¡Competencia iniciada!');
      });
      break;
      
    case 'competencia_detenida':
      setState(() {
        competenciaEnCurso = false;
        mostrarNotificacion('Competencia finalizada');
      });
      break;
  }
}
```

¡Ahora tu sistema es más seguro y robusto! 🚀
