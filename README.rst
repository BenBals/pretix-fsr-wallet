VerDE Wallet Pretix Payment Plugin
==========================

**This plugin has been deprecated in favour of our** `pretix Wallet`_ **plugin.**

This is a plugin for `pretix`_. 

Custom payment provider for wallet.myhpi.de, built for the FSR Digital Engineering at Uni Potsdam

Development setup
-----------------

1. Make sure that you have a working `pretix development setup`_.

2. Clone this repository.

3. Activate the virtual environment you use for pretix development.

4. Install dependencies ``pip install -r requirements.txt``

4. Execute ``pip install -e .`` within this directory to register this application with pretix's plugin registry.

5. Execute ``make`` within this directory to compile translations.

6. Restart your local pretix server. You can now use the plugin from this repository for your events by enabling it in
   the 'plugins' tab in the settings.

This plugin has CI set up to enforce a few code style rules. To check locally, you need these packages installed::

    pip install flake8 isort black docformatter

To check your plugin for rule violations, run::

    docformatter --check -r .
    black --check .
    isort -c .
    flake8 .

You can auto-fix some of these issues by running::

    docformatter -r .
    isort .
    black .

To automatically check for these issues before you commit, you can run ``.install-hooks``.

Configuration
-------------

You must provide configuration details and secrets in the settings for this plugin to work.

1. Create an OIDC provider at `oidc.hpi.de`, copy the client id and secret. Add ``[pretix-url]/wallet/return/`` to the redirect urls.
2. Copy the ``sig-rs-0`` key from `https://oidc.hpi.de/certs`.
3. Create a terminal at `wallet.myhpi.de`, copy the API key.

License
-------

Released under the terms of the Apache License 2.0

.. _pretix: https://github.com/pretix/pretix
.. _pretix development setup: https://docs.pretix.eu/en/latest/development/setup.html
.. _pretix Wallet: http://github.com/fsr-de/pretix-wallet