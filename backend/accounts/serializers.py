from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Announcement, AuditLog, Role, User


class UserSerializer(serializers.ModelSerializer):
    """Read representation of a user. Never exposes password hashes."""

    role_label = serializers.CharField(source="get_role_display", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True, default=None)
    department = serializers.CharField(source="employee.department.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "role", "role_label", "phone", "job_title",
            "is_active", "must_change_password", "last_seen_at", "created_at",
            "employee_code", "department",
        ]
        read_only_fields = ["id", "created_at", "last_seen_at", "must_change_password"]


class UserWriteSerializer(serializers.ModelSerializer):
    """Admin-only create/update. Password is hashed, never echoed back."""

    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "phone", "job_title",
                  "is_active", "password"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_role(self, value):
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        # Only an admin may mint another admin; HR cannot escalate privileges.
        if value == Role.ADMIN and actor and not actor.is_admin_role:
            raise serializers.ValidationError("Only an administrator can grant the ADMIN role.")
        return value

    def validate_email(self, value):
        return value.lower().strip()

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "A password is required for a new user."})
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        # Guard: an admin must not demote or deactivate themselves and lock
        # everyone out of user management.
        request = self.context.get("request")
        actor = getattr(request, "user", None)
        if actor and actor.pk == instance.pk:
            if validated_data.get("is_active") is False:
                raise serializers.ValidationError({"is_active": "You cannot deactivate your own account."})
            if validated_data.get("role") and validated_data["role"] != Role.ADMIN and instance.is_admin_role:
                raise serializers.ValidationError({"role": "You cannot remove your own admin role."})
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class MeSerializer(serializers.ModelSerializer):
    """What the logged-in user may change about themselves."""

    role_label = serializers.CharField(source="get_role_display", read_only=True)
    permissions = serializers.SerializerMethodField()
    employee = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "role_label", "phone", "job_title",
                  "permissions", "employee", "must_change_password", "last_seen_at", "created_at"]
        read_only_fields = ["id", "email", "role", "created_at", "last_seen_at",
                            "must_change_password"]

    def get_permissions(self, obj):
        return {
            "can_manage_people": obj.can_manage_people,
            "can_approve_leave": obj.can_approve_leave,
            "is_admin": obj.is_admin_role,
            "is_manager": obj.is_manager_role,
        }

    def get_employee(self, obj):
        emp = getattr(obj, "employee", None)
        if not emp:
            return None
        return {
            "id": emp.id,
            "employee_code": emp.employee_code,
            "designation": emp.designation,
            "department": emp.department.name if emp.department else None,
            "status": emp.status,
        }

    @transaction.atomic
    def update(self, instance, validated_data):
        """Save the account and keep the linked employee record in step.

        The login account and the employee record are two rows; if a person
        changes their name in the portal, HR's directory must not keep showing
        the old one. They are updated together or not at all.
        """
        user = super().update(instance, validated_data)

        employee = getattr(user, "employee", None)
        if employee:
            changed = []
            if "full_name" in validated_data:
                employee.full_name = validated_data["full_name"]
                changed.append("full_name")
            if "phone" in validated_data:
                employee.phone = validated_data["phone"]
                changed.append("phone")
            if "job_title" in validated_data:
                employee.designation = validated_data["job_title"]
                changed.append("designation")
            if changed:
                employee.save(update_fields=changed + ["updated_at"])

        if validated_data:
            from .models import AuditLog

            AuditLog.record(
                user, AuditLog.Action.UPDATE, "user",
                f"{user.full_name} updated their own profile "
                f"({', '.join(validated_data.keys())})",
                user.pk,
            )
        return user


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return user


class LoginSerializer(TokenObtainPairSerializer):
    """Adds the user profile to the token response so the SPA needs one call."""

    def validate(self, attrs):
        if "email" in attrs and isinstance(attrs["email"], str):
            attrs["email"] = attrs["email"].lower().strip()
        data = super().validate(attrs)
        # Same shape as GET /auth/me/ so the SPA needs one code path for the
        # signed-in user, whether it came from login or a page refresh.
        data["user"] = MeSerializer(self.user, context=self.context).data
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["name"] = user.full_name
        return token


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.full_name", read_only=True, default="System")
    author_role = serializers.CharField(source="author.role", read_only=True, default="")

    class Meta:
        model = Announcement
        fields = ["id", "title", "body", "is_pinned", "author", "author_name",
                  "author_role", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True, default="System")
    actor_role = serializers.CharField(source="actor.role", read_only=True, default="")
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "actor_name", "actor_role", "action", "action_label",
                  "entity", "entity_id", "summary", "created_at"]
        read_only_fields = fields
