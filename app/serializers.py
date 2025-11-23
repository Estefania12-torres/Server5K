from rest_framework import serializers
from .models import Competencia, Equipo, Juez, RegistroTiempo


class CompetenciaSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Competencia - Solo campos básicos"""
    
    class Meta:
        model = Competencia
        fields = [
            'id',
            'nombre',
            'fecha_hora',
            'categoria',
            'activa',
            'en_curso',
            'fecha_inicio',
            'fecha_fin',
        ]
        read_only_fields = ['id', 'fecha_inicio', 'fecha_fin']


class JuezMeSerializer(serializers.ModelSerializer):
    """Serializer para el endpoint /me - Solo información personal del juez autenticado"""
    
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Juez
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'full_name',
            'email',
            'telefono',
        ]
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class EquipoSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Equipo - Solo campos básicos"""
    
    class Meta:
        model = Equipo
        fields = [
            'id',
            'nombre',
            'dorsal',
            'juez_asignado',
        ]
        read_only_fields = ['id']


class RegistroTiempoSerializer(serializers.ModelSerializer):
    """Serializer para el modelo RegistroTiempo"""
    
    class Meta:
        model = RegistroTiempo
        fields = [
            'id_registro',
            'equipo',
            'tiempo',
            'timestamp',
            'horas',
            'minutos',
            'segundos',
            'milisegundos',
        ]
        read_only_fields = ['id_registro']
    
    def validate_tiempo(self, value):
        """Valida que el tiempo sea positivo"""
        if value < 0:
            raise serializers.ValidationError("El tiempo no puede ser negativo")
        return value


class SincronizarRegistrosSerializer(serializers.Serializer):
    """Serializer para la sincronización de múltiples registros"""
    equipo_id = serializers.IntegerField()
    registros = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=15
    )
    
    def validate_equipo_id(self, value):
        """Valida que el equipo exista"""
        from .models import Equipo
        if not Equipo.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"El equipo con ID {value} no existe")
        return value
    
    def validate_registros(self, value):
        """Valida la estructura de cada registro"""
        for registro in value:
            if 'tiempo' not in registro:
                raise serializers.ValidationError("Cada registro debe tener el campo 'tiempo'")
            if 'timestamp' not in registro:
                raise serializers.ValidationError("Cada registro debe tener el campo 'timestamp'")
            
            # Validar que tiempo sea positivo
            if registro['tiempo'] < 0:
                raise serializers.ValidationError("El tiempo no puede ser negativo")
        
        return value