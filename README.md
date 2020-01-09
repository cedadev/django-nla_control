django-nla_control
==================

Neil Massey and Sam Pepler

neil.massey@stfc.ac.uk

django-nla_control contains a Django application to control and manage the Near Line Archive (NLA) system at CEDA.

Some files at CEDA are stored only on tape, and not on disk.  Therefore, users cannot access them in the usual manner.

These files are moved to tape due to the large size of their dataset, for example, Sentinel and CMIP data.

The NLA allows users to temporarily restore files so that they can be accessed via the usual methods (MOLES / download / DAP / JASMIN mount point).

Installation
------------
The app is installed from an ansible playbook available only to CEDA staff members on the local gitlab repository (breezy).

Building the documentation
--------------------------
1. Install the app on a Vagrant VM using the ansible playbook
1. ssh into the vagrant box
1. activate the virtual env at `~/vagrant/NLA/venv/bin/activate`
1. `pip install sphinx`
1. `pip install sphinxcontrib-httpdomain`
1. `pip install rst2pdf`
1. `pip install sphinx_rtd_theme`
1. go to the `docs` directory
1. `make html`
