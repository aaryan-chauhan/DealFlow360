from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Company, Customer, Membership, Role, User


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name"]


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "label"]


class MembershipSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    role = RoleSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "company", "role", "is_active_default"]


class UserSerializer(serializers.ModelSerializer):
    memberships = MembershipSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "is_active", "memberships"]


class CustomerSerializer(serializers.ModelSerializer):
    quotation_count = serializers.IntegerField(source="quotations.count", read_only=True)
    has_portal_login = serializers.BooleanField(source="has_usable_password", read_only=True)
    # Write-only and optional: a rep may set/replace the customer's self-service portal
    # password here (spec A1), or leave it blank to change nothing (never blank an
    # existing password just because the field wasn't sent on an unrelated edit).
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Customer
        fields = [
            "id", "name", "tier", "email", "location", "quotation_count", "created_at",
            "has_portal_login", "password",
        ]

    def validate_email(self, value):
        company = self.context["membership"].company
        qs = Customer.objects.filter(company=company, email__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A customer with this email already exists.")
        return value.strip()

    def validate_password(self, value):
        if value:
            validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", "")
        customer = Customer(**validated_data)
        if password:
            customer.set_password(password)
        customer.save()
        return customer

    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password_hash", "updated_at"])
        return instance


class SignupSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    company_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        company = Company.objects.create(name=validated_data["company_name"])
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
        )
        # The person who creates the tenant owns its configuration.
        Membership.objects.create(
            user=user,
            company=company,
            role=Role.objects.get(code=Role.ADMIN),
            is_active_default=True,
        )
        return user


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
