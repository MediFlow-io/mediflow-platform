from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    class Meta:
        model = User
        fields = ("id", "username", "display_name", "first_name", "last_name", "email", "role", "is_active", "last_login", "password")
        read_only_fields = ("id", "last_login")
    def validate(self, attrs):
        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "A password is required for new accounts."})
        if password:
            try:
                validate_password(password, self.instance or User(username=attrs.get("username", "")))
            except DjangoValidationError as error:
                raise serializers.ValidationError({"password": list(error.messages)})
        return attrs
    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for key, value in validated_data.items(): setattr(instance, key, value)
        if password: instance.set_password(password)
        instance.save()
        return instance
