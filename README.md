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
