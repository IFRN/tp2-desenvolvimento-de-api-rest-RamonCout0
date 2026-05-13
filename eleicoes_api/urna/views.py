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


