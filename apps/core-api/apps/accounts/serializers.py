from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    class Meta:
        model = User
        fields = ("id", "username", "display_name", "first_name", "last_name", "role", "is_active", "password")
        read_only_fields = ("id",)
    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for key, value in validated_data.items(): setattr(instance, key, value)
        if password: instance.set_password(password)
        instance.save()
        return instance
