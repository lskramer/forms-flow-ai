"""This manages Form ProcessMapper Database Models."""

from __future__ import annotations

from http import HTTPStatus

from flask import current_app
from flask_sqlalchemy.query import Query
from formsflow_api_utils.utils import (
    DEFAULT_PROCESS_KEY,
    DEFAULT_PROCESS_NAME,
    FILTER_MAPS,
    validate_sort_order_and_order_by,
)
from formsflow_api_utils.utils.enums import FormProcessMapperStatus
from formsflow_api_utils.utils.user_context import UserContext, user_context
from sqlalchemy import UniqueConstraint, and_, desc, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql.expression import text

from .audit_mixin import AuditDateTimeMixin, AuditUserMixin
from .base_model import BaseModel
from .db import db


class FormProcessMapper(AuditDateTimeMixin, AuditUserMixin, BaseModel, db.Model):
    """This class manages form process mapper information."""

    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.String(50), nullable=False)
    form_name = db.Column(db.String(100), nullable=False)
    form_type = db.Column(db.String(20), nullable=False)
    parent_form_id = db.Column(db.String(50), nullable=False)
    process_key = db.Column(db.String(50), nullable=True, default=DEFAULT_PROCESS_KEY)
    process_name = db.Column(
        db.String(100), nullable=True, default=DEFAULT_PROCESS_NAME
    )
    status = db.Column(db.String(10), nullable=True)
    comments = db.Column(db.String(300), nullable=True)
    tenant = db.Column(db.String(100), nullable=True)
    process_tenant = db.Column(
        db.String(),
        nullable=True,
        comment="Tenant ID Mapped to process definition. "
        "This will be null for shared process definition.",
    )
    application = db.relationship(
        "Application", backref="form_process_mapper", lazy=True
    )
    is_anonymous = db.Column(db.Boolean, nullable=True)
    deleted = db.Column(db.Boolean, nullable=True, default=False)
    task_variable = db.Column(JSON, nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    description = db.Column(db.String, nullable=True)

    __table_args__ = (
        UniqueConstraint("form_id", "version", "tenant", name="_form_version_uc"),
    )

    @classmethod
    def create_from_dict(cls, mapper_info: dict) -> FormProcessMapper:
        """Create new mapper between form and process."""
        try:
            if mapper_info:
                mapper = FormProcessMapper()
                mapper.form_id = mapper_info["form_id"]
                mapper.form_name = mapper_info["form_name"]
                mapper.form_type = mapper_info["form_type"]
                mapper.parent_form_id = mapper_info["parent_form_id"]
                mapper.process_key = mapper_info.get("process_key")
                mapper.process_name = mapper_info.get("process_name")
                mapper.status = mapper_info.get("status")
                mapper.comments = mapper_info.get("comments")
                mapper.created_by = mapper_info["created_by"]
                mapper.tenant = mapper_info.get("tenant")
                mapper.process_tenant = mapper_info.get("process_tenant")
                mapper.is_anonymous = mapper_info.get("is_anonymous")
                mapper.task_variable = mapper_info.get("task_variable")
                mapper.version = mapper_info.get("version")
                mapper.description = mapper_info.get("description")
                mapper.save()
                return mapper
        except Exception as err:  # pylint: disable=broad-except
            current_app.logger.critical(err)
        response, status = {
            "type": "Bad Request Error",
            "message": "Invalid application request passed",
        }, HTTPStatus.BAD_REQUEST
        return response, status

    def update(self, mapper_info: dict):
        """Update form process mapper."""
        self.update_from_dict(
            [
                "form_id",
                "form_name",
                "form_type",
                "form_revision_number",
                "process_key",
                "process_name",
                "status",
                "comments",
                "modified_by",
                "is_anonymous",
                "task_variable",
                "process_tenant",
                "description",
            ],
            mapper_info,
        )
        self.commit()

    def mark_inactive(self):
        """Mark form process mapper as inactive and deleted."""
        self.status: str = str(FormProcessMapperStatus.INACTIVE.value)
        self.deleted: bool = True
        self.commit()

    def mark_unpublished(self):
        """Mark form process mapper as inactive."""
        self.status: str = str(FormProcessMapperStatus.INACTIVE.value)
        self.commit()

    @classmethod
    def find_all(cls, page_number, limit):
        """Fetch all the form process mappers."""
        if page_number == 0:
            query = cls.query.order_by(FormProcessMapper.id.desc()).all()
        else:
            query = (
                cls.query.order_by(FormProcessMapper.id.desc())
                .paginate(page=page_number, per_page=limit, error_out=False)
                .items
            )
        return query

    @classmethod
    def filter_conditions(cls, **filters):
        """This method creates dynamic filter conditions based on the input param."""
        filter_conditions = []
        for key, value in filters.items():
            if value:
                filter_map = FILTER_MAPS[key]
                condition = FormProcessMapper.create_filter_condition(
                    model=FormProcessMapper,
                    column_name=filter_map["field"],
                    operator=filter_map["operator"],
                    value=value,
                )
                filter_conditions.append(condition)
        query = cls.query.filter(*filter_conditions) if filter_conditions else cls.query
        return query

    @classmethod
    @user_context
    def access_filter(cls, query: Query, **kwargs):
        """Modifies the query to include active and tenant check."""
        if not isinstance(query, Query):
            raise TypeError("Query object must be of type Query")
        user: UserContext = kwargs["user"]
        tenant_key: str = user.tenant_key
        active = query.filter(
            FormProcessMapper.status == str(FormProcessMapperStatus.ACTIVE.value)
        )
        if tenant_key is not None:
            active = active.filter(FormProcessMapper.tenant == tenant_key)
        return active

    @classmethod
    def get_latest_form_mapper_ids(cls):
        """Getting latest mapper id of a form, based on parentFormId."""
        # Execute a query to retrieve the maximum ID of the form mapper and the parent form ID
        # Since each form has one or more versions so we need latest from based on parentId
        return (
            db.session.query(
                func.max(cls.id).label("id"),  # pylint: disable=not-callable
                cls.parent_form_id,
            )
            # Group the results by the parent form ID
            .group_by(cls.parent_form_id)
            # Retrieve all the results as a list of tuples
            .all()
        )

    @classmethod
    def find_all_forms(
        cls,
        page_number=None,
        limit=None,
        sort_by=None,
        sort_order=None,
        form_ids=None,
        is_active=None,
        form_type=None,
        **filters,
    ):  # pylint: disable=too-many-arguments
        """Fetch all active and inactive forms which are not deleted."""
        # Get latest row for each form_id group
        filtered_form_query = cls.get_latest_form_mapper_ids()
        filtered_form_ids = [
            data.id for data in filtered_form_query if data.parent_form_id in form_ids
        ]
        query = cls.filter_conditions(**filters)
        query = query.filter(
            and_(FormProcessMapper.deleted.is_(False)),
            FormProcessMapper.id.in_(filtered_form_ids),
        )
        # form type is list of type to filter the form
        if form_type:
            query = query.filter(FormProcessMapper.form_type.in_(form_type))

        if is_active is not None:
            value = FormProcessMapperStatus["ACTIVE" if is_active else "INACTIVE"].value
            query = query.filter(FormProcessMapper.status == value)

        query = cls.tenant_authorization(query=query)
        sort_by, sort_order = validate_sort_order_and_order_by(sort_by, sort_order)
        if sort_by and sort_order:
            query = query.order_by(text(f"form_process_mapper.{sort_by} {sort_order}"))

        total_count = query.count()
        query = query.with_entities(
            cls.id,
            cls.process_key,
            cls.form_id,
            cls.form_name,
            cls.modified,
            cls.status,
            cls.is_anonymous,
            cls.form_type,
            cls.created,
            cls.description,
        )
        limit = total_count if limit is None else limit
        query = query.paginate(page=page_number, per_page=limit, error_out=False)
        return query.items, total_count

    @classmethod
    def find_all_active_by_formid(
        cls,
        page_number=None,
        limit=None,
        sort_by=None,
        sort_order=None,
        form_ids=None,
        **filters,
    ):  # pylint: disable=too-many-arguments
        """Fetch all active form process mappers by authorized forms."""
        # Get latest row for each form_id group
        filtered_form_query = cls.get_latest_form_mapper_ids()
        filtered_form_ids = [
            data.id for data in filtered_form_query if data.parent_form_id in form_ids
        ]
        query = cls.filter_conditions(**filters)
        query = query.filter(
            FormProcessMapper.id.in_(filtered_form_ids),
        )
        query = cls.access_filter(query=query)
        sort_by, sort_order = validate_sort_order_and_order_by(sort_by, sort_order)
        if sort_by and sort_order:
            query = query.order_by(text(f"form_process_mapper.{sort_by} {sort_order}"))

        total_count = query.count()
        query = query.with_entities(
            cls.id,
            cls.process_key,
            cls.form_id,
            cls.form_name,
            cls.modified,
            cls.description,
        )
        limit = total_count if limit is None else limit
        query = query.paginate(page=page_number, per_page=limit, error_out=False)
        return query.items, total_count

    @classmethod
    def find_all_active(
        cls,
        page_number=None,
        limit=None,
        sort_by=None,
        sort_order=None,
        process_key=None,
        **filters,
    ):  # pylint: disable=too-many-arguments
        """Fetch all active form process mappers."""
        query = cls.filter_conditions(**filters)
        if process_key is not None:
            query = query.filter(FormProcessMapper.process_key.in_(process_key))
        query = cls.access_filter(query=query)
        sort_by, sort_order = validate_sort_order_and_order_by(sort_by, sort_order)
        if sort_by and sort_order:
            query = query.order_by(text(f"form_process_mapper.{sort_by} {sort_order}"))

        total_count = query.count()
        query = query.with_entities(
            cls.id,
            cls.process_key,
            cls.form_id,
            cls.form_name,
        )
        limit = total_count if limit is None else limit
        query = query.paginate(page=page_number, per_page=limit, error_out=False)
        return query.items, total_count

    @classmethod
    def find_all_count(cls):
        """Fetch the total active form process mapper which are active."""
        return cls.query.filter(
            FormProcessMapper.status == str(FormProcessMapperStatus.ACTIVE.value)
        ).count()

    @classmethod
    def find_form_by_id_active_status(cls, form_process_mapper_id) -> FormProcessMapper:
        """Find active form process mapper that matches the provided id."""
        return cls.query.filter(
            and_(
                FormProcessMapper.id == form_process_mapper_id,
                FormProcessMapper.status == str(FormProcessMapperStatus.ACTIVE.value),
            )
        ).first()  # pylint: disable=no-member

    @classmethod
    def find_form_by_id(cls, form_process_mapper_id) -> FormProcessMapper:
        """Find form process mapper that matches the provided id."""
        return cls.query.filter(FormProcessMapper.id == form_process_mapper_id).first()

    @classmethod
    def find_form_by_form_id(cls, form_id) -> FormProcessMapper:
        """Find form process mapper that matches the provided form_id."""
        return (
            cls.query.filter(
                FormProcessMapper.form_id == form_id,
            )
            .order_by(desc(FormProcessMapper.version))
            .limit(1)
            .first()
        )  # pylint: disable=no-member

    @classmethod
    @user_context
    def find_mapper_by_form_id_and_version(
        cls, form_id: int, version: int, **kwargs
    ) -> FormProcessMapper:
        """
        Return the form process mapper with given form_id and version.

        : form_id : form_id corresponding to the mapper
        : version : version corresponding to the mapper
        """
        user: UserContext = kwargs["user"]
        tenant_key: str = user.tenant_key
        query = cls.query.filter(
            and_(
                cls.form_id == form_id, cls.version == version, cls.tenant == tenant_key
            )
        ).first()
        return query

    @classmethod
    @user_context
    def tenant_authorization(cls, query: Query, **kwargs):
        """Modifies the query to include tenant check if needed."""
        tenant_auth_query: Query = query
        user: UserContext = kwargs["user"]
        tenant_key: str = user.tenant_key
        if not isinstance(query, Query):
            raise TypeError("Query object must be of type Query")
        if tenant_key is not None:
            tenant_auth_query = tenant_auth_query.filter(cls.tenant == tenant_key)
        return tenant_auth_query
