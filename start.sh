#!/usr/bin/env bash

gunicorn medburg_crm.wsgi:application