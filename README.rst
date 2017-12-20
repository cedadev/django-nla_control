=====
NLT Control
=====

Near Line tape control system to work with storage-D only archive. 

Quick start
-----------

1. Add "nla_control" to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = (
        ...
        'nla_control',
    )

2. Include the URLconf in your project urls.py like this::

    url(r'^nla_control/', include('nla_control.urls')),

3. Run `python manage.py migrate` to create the models.

4. Start the development server and visit http://127.0.0.1:8000/admin/
   to create content (you'll need the Admin app enabled).

