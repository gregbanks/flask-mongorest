import json
import mimerender
import mongoengine
from flask import request
from flask.ext.views.base import View
from werkzeug.routing import NotFound
from werkzeug.exceptions import Unauthorized
from flask.ext.mongorest.resources import Resource
from flask.ext.mongorest.utils import MongoEncoder
from flask.ext.mongorest.exceptions import ValidationError


mimerender = mimerender.FlaskMimeRender()
render_json = lambda **payload: json.dumps(payload, cls=MongoEncoder)

class ResourceView(View):
    resource = None
    methods = []
    authentication_methods = []

    def __init__(self):
        assert(self.resource and self.methods)

    @mimerender(default='json', json = render_json)
    def dispatch_request(self, *args, **kwargs):
        self._resource = self.resource()
        authorized = True if len(self.authentication_methods) == 0 else False
        for authentication_method in self.authentication_methods:
            if authentication_method().authorized():
                authorized = True
        if not authorized:
            raise Unauthorized 

        try:
            return super(ResourceView, self).dispatch_request(*args, **kwargs)
        except ValidationError, e:
            return e.message, '400 Bad Request' #TODO fix in mimerender
        except mongoengine.queryset.DoesNotExist:
            raise NotFound()

    def get(self, **kwargs):
        pk = kwargs.pop('pk', None)
        if pk is None:
            objs = self._resource.get_objects()
            ret = [self._resource.serialize(obj, request.args) for obj in objs]
            return {'data': ret}
        else:
            obj = self._resource.get_object(pk)
            ret = self._resource.serialize(obj, request.args)
            return ret

    def post(self, **kwargs):
        if 'pk' in kwargs:
            raise NotFound("Did you mean to use PUT?")
        self._resource.validate_request()
        obj = self._resource.create_object()
        ret = self._resource.serialize(obj, request.args)
        return ret

    def put(self, **kwargs):
        pk = kwargs.pop('pk', None)
        if pk is None:
            # Bulk update where the body contains the new values for certain
            # fields.

            # Currently, fetches all the objects and validate them separately.
            # If one of them fails, a ValidationError for this object will be
            # triggered.
            # Ideally, this would be translated into an update statement for
            # performance reasons and would perform the update either for all
            # objects, or for none, if (generic) validation fails. Since this
            # is a bulk update, only the count of objects which were updated is
            # returned.

            objs = self._resource.get_objects()
            count = 0
            try:
                for obj in objs:
                    self._resource.validate_request(obj)
                    obj = self._resource.update_object(obj)
                    obj.save()
                    count += 1
            except ValidationError, e:
                e.message['count'] = count
                raise e
            else:
                return {'count': count}
        else:
            obj = self._resource.get_object(pk)
            self._resource.validate_request(obj)
            obj = self._resource.update_object(obj)
            ret = self._resource.serialize(obj, request.args)
            return ret

    def delete(self, **kwargs):
        pk = kwargs.pop('pk', None)
        obj = self._resource.get_object(pk)
        self._resource.delete_object(obj)
        return {}
