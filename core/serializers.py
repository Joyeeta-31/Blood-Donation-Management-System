# core/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    DonorProfile, BloodBank, BloodInventory,
    DonationRequest, DonationHistory, BLOOD_GROUPS
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=6)
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'password', 'role')
        read_only_fields = ('role',)  # Only set role from backend if needed

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class DonorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = DonorProfile
        fields = '__all__'

    def validate_blood_group(self, value):
        valid = [b[0] for b in BLOOD_GROUPS]
        if value not in valid:
            raise serializers.ValidationError("Invalid blood group.")
        return value


class BloodBankSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodBank
        fields = '__all__'


class BloodInventorySerializer(serializers.ModelSerializer):
    blood_bank = BloodBankSerializer(read_only=True)
    
    class Meta:
        model = BloodInventory
        fields = '__all__'
        read_only_fields = ('blood_bank',)


class DonationRequestSerializer(serializers.ModelSerializer):
    requester = serializers.PrimaryKeyRelatedField(read_only=True)
    status = serializers.CharField(read_only=True)
    
    class Meta:
        model = DonationRequest
        fields = '__all__'

    def validate_blood_group(self, value):
        valid = [b[0] for b in BLOOD_GROUPS]
        if value not in valid:
            raise serializers.ValidationError("Invalid blood group.")
        return value

    def validate_units(self, value):
        if value <= 0:
            raise serializers.ValidationError("Units must be greater than zero.")
        return value


class DonationHistorySerializer(serializers.ModelSerializer):
    donor = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = DonationHistory
        fields = '__all__'
