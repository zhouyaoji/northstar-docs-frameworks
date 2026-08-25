Create an environment
=====================

This example creates a non-production environment from the ``web-service``
profile. The API is fictional and exists only to make the documentation feel
concrete.

Before you begin
----------------

* Confirm that the ``web-service`` profile exists.
* Choose a provider and region approved for your team.
* Use an API token with permission to create environments.

Send the request
----------------

.. code-block:: bash

   curl --request POST https://api.northstar.example/v1/environments \
     --header "Authorization: Bearer $NORTHSTAR_TOKEN" \
     --header "Content-Type: application/json" \
     --data '{
       "name": "payments-sandbox",
       "profile": "web-service",
       "provider": "aws",
       "region": "us-west-2"
     }'

Northstar returns ``202 Accepted`` while it provisions the environment. Use the
returned environment identifier to retrieve status.

Verify the result
-----------------

.. code-block:: bash

   curl https://api.northstar.example/v1/environments/env_123 \
     --header "Authorization: Bearer $NORTHSTAR_TOKEN"

If the status is ``ready``, hand the environment to the application team. If it
is ``failed``, inspect the validation errors before retrying.

For request and response conventions, see :doc:`../reference/api-conventions`.
