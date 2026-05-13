from django.shortcuts import render
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Eleitor, Eleicao, Candidato, AptidaoEleitor, RegistroVotacao, Voto
from .serializers import *
import hashlib
import secrets
import qrcode
from io import BytesIO
from django.http import HttpResponse
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny


class EleitorViewSet(viewsets.ModelViewSet):
    queryset = Eleitor.objects.all()
    serializer_class = EleitorSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['ativo']
    search_fields = ['nome', 'email', 'cpf']


class EleicaoViewSet(viewsets.ModelViewSet):
    queryset = Eleicao.objects.all()
    serializer_class = EleicaoSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'tipo', 'criada_por']
    search_fields = ['titulo']
    ordering_fields = ['data_inicio']
    ordering = ['data_inicio']

    @action(detail=True, methods=['post'])
    def votar(self, request, pk=None):
        eleicao = self.get_object()
        data = request.data.copy()
        data['eleicao_id'] = eleicao.id
        serializer = VotacaoInputSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        valid_data = serializer.validated_data
        try:
            with transaction.atomic():
                try:
                    RegistroVotacao.objects.create(
                        eleitor_id=valid_data['eleitor_id'],
                        eleicao=eleicao
                    )
                except IntegrityError:
                    return Response(
                        {'mensagem': 'Eleitor já votou nesta eleição'},
                        status=status.HTTP_409_CONFLICT
                    )

                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode()).hexdigest()

                voto = Voto.objects.create(
                    eleicao=eleicao,
                    candidato_id=valid_data.get('candidato_id'),
                    em_branco=valid_data.get('em_branco', False),
                    comprovante_hash=token_hash
                )

                candidato_info = "BRANCO"
                if voto.candidato:
                    candidato_info = f"{voto.candidato.nome_urna} (#{voto.candidato.numero})"

                return Response({
                    "mensagem": "Voto registrado com sucesso. Guarde o seu comprovante.",
                    "comprovante": {
                        "token": token,
                        "eleicao": eleicao.titulo,
                        "candidato": candidato_info,
                        "data_hora": voto.data_hora,
                        "qr_code_url": f"/eleicoes_api/comprovantes/qr/?token={token}"
                    }
                }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'erro': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def abrir(self, request, pk=None):
        eleicao = self.get_object()
        if eleicao.status != 'rascunho':
            return Response({'erro': 'Eleição não pode ser aberta'}, status=status.HTTP_400_BAD_REQUEST)
        if eleicao.candidatos.count() < 2:
            return Response({'erro': 'Eleição deve ter pelo menos 2 candidatos'}, status=status.HTTP_400_BAD_REQUEST)
        if eleicao.aptos.count() < 1:
            return Response({'erro': 'Eleição deve ter pelo menos 1 eleitor apto'}, status=status.HTTP_400_BAD_REQUEST)
        eleicao.status = 'aberta'
        eleicao.save()
        serializer = self.get_serializer(eleicao)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def encerrar(self, request, pk=None):
        eleicao = self.get_object()
        if eleicao.status != 'aberta':
            return Response({'erro': 'Eleição não pode ser encerrada'}, status=status.HTTP_400_BAD_REQUEST)
        eleicao.status = 'encerrada'
        eleicao.save()
        return Response({'mensagem': 'Eleição encerrada com sucesso'})

    @action(detail=True, methods=['get'])
    def apuracao(self, request, pk=None):
        eleicao = self.get_object()
        if eleicao.status not in ['encerrada', 'apurada']:
            return Response({'erro': 'Eleição não está apta para apuração'}, status=status.HTTP_403_FORBIDDEN)
        
        total_aptos = eleicao.aptos.count()
        total_votantes = RegistroVotacao.objects.filter(eleicao=eleicao).count()
        total_abstencoes = total_aptos - total_votantes
        
        votos_validos = Voto.objects.filter(eleicao=eleicao, em_branco=False).count()
        votos_brancos = Voto.objects.filter(eleicao=eleicao, em_branco=True).count()
        
        candidatos = []
        max_votos = 0
        vencedores = []
        
        for candidato in eleicao.candidatos.all():
            votos_candidato = Voto.objects.filter(eleicao=eleicao, candidato=candidato).count()
            percentual = (votos_candidato / votos_validos * 100) if votos_validos > 0 else 0
            candidatos.append({
                'candidato': candidato.nome_urna,
                'numero': candidato.numero,
                'votos': votos_candidato,
                'percentual': round(percentual, 2)
            })
            if votos_candidato > max_votos:
                max_votos = votos_candidato
                vencedores = [candidato.nome_urna]
            elif votos_candidato == max_votos:
                vencedores.append(candidato.nome_urna)
        
        candidatos.sort(key=lambda x: x['votos'], reverse=True)
        for i, cand in enumerate(candidatos, 1):
            cand['posicao'] = i
        
        comparecimento_pct = (total_votantes / total_aptos * 100) if total_aptos > 0 else 0
        
        if eleicao.status == 'encerrada':
            eleicao.status = 'apurada'
            eleicao.save()
        
        return Response({
            'eleicao': eleicao.titulo,
            'total_aptos': total_aptos,
            'total_votantes': total_votantes,
            'total_abstencoes': total_abstencoes,
            'votos_validos': votos_validos,
            'votos_brancos': votos_brancos,
            'comparecimento_pct': round(comparecimento_pct, 2),
            'resultado': candidatos,
            'vencedores': vencedores,
            'houve_empate': len(vencedores) > 1
        })

    @action(detail=True, methods=['get'])
    def votantes(self, request, pk=None):
        eleicao = self.get_object()
        compareceu = request.query_params.get('compareceu', 'true').lower() == 'true'
        
        if compareceu:
            registros = RegistroVotacao.objects.filter(eleicao=eleicao).select_related('eleitor')
            votantes = []
            for reg in registros:
                cpf_mascarado = reg.eleitor.cpf[:3] + '***' + reg.eleitor.cpf[7:11] + '**' + reg.eleitor.cpf[12:]
                votantes.append({
                    'nome': reg.eleitor.nome,
                    'cpf': cpf_mascarado,
                    'data_hora': reg.data_hora
                })
        else:
            aptos_ids = set(eleicao.aptos.values_list('id', flat=True))
            votaram_ids = set(RegistroVotacao.objects.filter(eleicao=eleicao).values_list('eleitor_id', flat=True))
            abstencoes_ids = aptos_ids - votaram_ids
            abstencoes = Eleitor.objects.filter(id__in=abstencoes_ids)
            votantes = []
            for eleitor in abstencoes:
                cpf_mascarado = eleitor.cpf[:3] + '***' + eleitor.cpf[7:11] + '**' + eleitor.cpf[12:]
                votantes.append({
                    'nome': eleitor.nome,
                    'cpf': cpf_mascarado
                })
        
        return Response(votantes)

    @action(detail=True, methods=['post'])
    def cadastrar_aptos(self, request, pk=None):
        eleicao = self.get_object()
        if eleicao.status != 'rascunho':
            return Response({'erro': 'Eleição deve estar em rascunho'}, status=status.HTTP_400_BAD_REQUEST)
        
        eleitores_ids = request.data.get('eleitores_ids', [])
        if not isinstance(eleitores_ids, list):
            return Response({'erro': 'eleitores_ids deve ser uma lista'}, status=status.HTTP_400_BAD_REQUEST)
        
        total_cadastrados = 0
        for eleitor_id in eleitores_ids:
            try:
                AptidaoEleitor.objects.get_or_create(eleicao=eleicao, eleitor_id=eleitor_id)
                total_cadastrados += 1
            except:
                pass  
        
        return Response({'total_cadastrados': total_cadastrados})

class CandidatoViewSet(viewsets.ModelViewSet):
    queryset = Candidato.objects.select_related('eleicao').all()
    serializer_class = CandidatoSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['eleicao', 'numero']
    search_fields = ['nome', 'nome_urna', 'partido_ou_chapa']
    ordering_fields = ['numero']
    ordering = ['numero']


class AptidaoEleitorViewSet(viewsets.ModelViewSet):
    queryset = AptidaoEleitor.objects.select_related('eleitor', 'eleicao').all()
    serializer_class = AptidaoEleitorSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['eleitor', 'eleicao']

class RegistroVotacaoViewSet(viewsets.ModelViewSet):
    queryset = RegistroVotacao.objects.select_related('eleitor', 'eleicao').all()
    serializer_class = RegistroVotacaoSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['eleicao']
    ordering_fields = ['data_hora']
    ordering = ['-data_hora']

class VotoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Voto.objects.all()
    serializer_class = VotoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['eleicao']


@api_view(['GET'])
@permission_classes([AllowAny])
def verificar_comprovante(request):
    token = request.query_params.get('token')
    if not token:
        return Response({'valido': False}, status=status.HTTP_400_BAD_REQUEST)

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        voto = Voto.objects.get(comprovante_hash=token_hash)
        candidato_info = "BRANCO"
        if voto.candidato:
            candidato_info = f"{voto.candidato.nome_urna} (#{voto.candidato.numero})"

        return Response({
            'eleicao': voto.eleicao.titulo,
            'candidato': candidato_info,
            'data_hora': voto.data_hora,
            'valido': True
        })
    except Voto.DoesNotExist:
        return Response({'valido': False, 'mensagem': 'Comprovante inválido'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def gerar_qr_code(request):
    token = request.query_params.get('token')
    verificacao_url = request.build_absolute_uri(f'/eleicoes_api/verificar-comprovante/?token={token}')
    img = qrcode.make(verificacao_url)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


