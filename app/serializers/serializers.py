from rest_framework import serializers
from app.models import Competencia, Equipo, Juez, RegistroTiempo


class CompetenciaSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Competencia - Solo campos básicos"""
    
    class Meta:
        model = Competencia
        fields = [
            'id',
            'name',
            'datetime',
            'is_active',
            'is_running',
            'started_at',
            'finished_at',
        ]
        read_only_fields = ['id', 'started_at', 'finished_at']


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
        ]
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class EquipoSerializer(serializers.ModelSerializer):
    """Serializer para el modelo Equipo - Solo campos básicos"""
    
    judge_username = serializers.CharField(source='judge.username', read_only=True)
    competition_id = serializers.IntegerField(source='competition.id', read_only=True)
    competition_name = serializers.CharField(source='competition.name', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    
    class Meta:
        model = Equipo
        fields = [
            'id',
            'name',
            'number',
            'category',
            'category_display',
            'competition_id',
            'competition_name',
            'judge_username',
        ]
        read_only_fields = ['id', 'competition_id', 'competition_name', 'judge_username', 'category_display']


class RegistroTiempoSerializer(serializers.ModelSerializer):
    """Serializer para el modelo RegistroTiempo"""
    
    class Meta:
        model = RegistroTiempo
        fields = [
            'record_id',
            'team',
            'time',
            'created_at',
            'hours',
            'minutes',
            'seconds',
            'milliseconds',
        ]
        read_only_fields = ['record_id']
    
    def validate_time(self, value):
        """Valida que el tiempo sea positivo"""
        if value < 0:
            raise serializers.ValidationError("El tiempo no puede ser negativo")
        return value


class SincronizarRegistrosSerializer(serializers.Serializer):
    """Serializer para la sincronización de múltiples registros"""
    team_id = serializers.IntegerField()
    registros = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=15
    )
    
    def validate_team_id(self, value):
        """Valida que el equipo exista"""
        from app.models import Equipo
        if not Equipo.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"El equipo con ID {value} no existe")
        return value
    
    def validate_registros(self, value):
        """Valida la estructura de cada registro"""
        for registro in value:
            if 'time' not in registro:
                raise serializers.ValidationError("Cada registro debe tener el campo 'time'")
            if 'created_at' not in registro:
                raise serializers.ValidationError("Cada registro debe tener el campo 'created_at'")
            
            # Validar que tiempo sea positivo
            if registro['time'] < 0:
                raise serializers.ValidationError("El tiempo no puede ser negativo")
        
        return value
