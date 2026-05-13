from rest_framework import serializers
from .models import *
from django.utils import timezone
import re

class EleitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Eleitor
        fields = '__all__'
    
    def validate_cpf(self, value):
        cpf_pattern = r'^\d{3}\.\d{3}\.\d{3}-\d{2}$'
        if not re.match(cpf_pattern, value):
            raise serializers.ValidationError("CPF deve estar no formato XXX.XXX.XXX-XX")
        return value
class EleicaoSerializer(serializers.ModelSerializer):
    status_display = serializers.Charfield(source=get_status_display, read_only=True)
    total_candidatos = serializers.SerializerMethodField()
    total_aptos = serializers.SerializerMethodField()

    class Meta:
        model = Eleicao
        fields =['id','titulo', 'data_inicio', 'data_fim','status','status_display','total_candidatos','total_aptos']

        def get_total_candidatos(self, obj):
            return obj.candidatos.count()
        
        def get_total_aptos(self, obj):
            return obj.aptos.count()

class CandidatoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidato
        fields = '__all__'

    def validate_numero(self, value):
        if value == 0:
            raise serializers.ValidationError("Número do candidato deve ser maior que zero.")
        return value

class RegistroVotacaoSerializer(serializers.ModelSerializer):
    eleitor_nome = serializers.ReadOnlyField(source='eleitor.nome')
    eleicao_titulo = serializers.ReadOnlyField(source='eleicao.titulo')

    class Meta:
        model = RegistroVotacao
        fields = '__all__'
        read_only_fields = ['eleitor', 'eleicao', 'data_voto']

class VotoSerializer(serializers.ModelSerializer):
    candidato_nome_urna = serializers.ReadOnlyField(source='candidato.nome_urna')
    em_branco_display = serializers.SerializerMethodField()

    class Meta:
        model = Voto
        exclude = ['comprovante_hash']
        read_only_fields =['id','eleicao','candidato', 'em_branco']
    def get_em_branco_display(self, obj):
        return 'BRANCO' if obj.em_branco else None

class VotacaoInputSerializer(serializers.Serializer):
    eleitor_id = serializers.IntegerField()
    eleicao_id = serializers.IntegerField()
    candidato_id = serializers.IntegerField(required=False)
    em_branco = serializers.BooleanField(default=False)

    def validate(self, data):
        canditato_id = data.get('candidato_id')
        em_branco = data.get('em_branco')

        if not candidato_id and not em_branco:
            raise serializers.ValidationError("informe um candidato ou selecione branco")
            if candidato_id and branco:
                raise serializers.ValidationError("não é possível votar nesse candidato e em branco, só pode um")
            try:
                eleicao =Eleicao.objects.get(pk=data['eleicao_id'])
                eleitor = Eleitor.objects.get(pk=data['eleitor_id'])
            except (Eleicao.DoesNotExist, Eleitor.DoesNotExist):
                    raise serializers.ValidationError("Eleição ou Eleitor não encontrado.")
            if eleicao.status != 'aberta':
                raise serializers.ValidationError("Eleição não está aberta para votação.")
            
            agora = timezone.now()
            if not(eleicao.data_inicio <= agora <= eleicao.data_fim):
                raise serializers.ValidationError("A eleição não está no período tente na data que foi selecionada")

            if not ApitidaoEleitor.objects.filter(eleicao=eleicao, eleitor=eleitor).exists():
                raise serializers.ValidationError("Eleitor não apto para votar nessa eleição.")
            
            if RegistroVotacao.objects.filter(eleicao=eleicao, eleitor=eleitor).exists():
                raise serializers.ValidationError("Eleitor já votou nessa eleição.")

            if candidato_id:
                try:
                    canditato = Candidato.objects.get(pk=candidato_id)
                    if canditato.eleicao_id != eleicao.id:
                        raise serializers.ValidationError("Candidato não pertence a essa eleição.")
                except Candidato.DoesNotExist:
                    raise serializers.ValidationError("Candidato não encontrado.")

            return data
            
            




