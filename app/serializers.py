from rest_framework import serializers
from .models import Competencia, Equipo, Juez


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