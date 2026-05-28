"""HTTP views for People.

The views are intentionally thin: they validate the request, delegate to a
selector/service, and serialize the result.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.people.api.serializers import (
    PersonDetailSerializer,
    PersonListSerializer,
)
from apps.people.selectors.person_selectors import (
    get_person_with_graph,
    list_people,
)


class PersonListView(ListAPIView):
    serializer_class = PersonListSerializer

    def get_queryset(self):
        return list_people()


class PersonDetailView(APIView):
    def get(self, request, pk: int):
        person = get_person_with_graph(pk)
        if person is None:
            return Response(
                {"detail": "Person not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(PersonDetailSerializer(person).data)
