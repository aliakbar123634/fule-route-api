
from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)

    def validate_start(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Start location cannot be empty."
            )

        return value

    def validate_destination(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Destination cannot be empty."
            )

        return value
