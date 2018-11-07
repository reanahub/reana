Changes
=======

Version 0.4.0 (2018-11-07)
--------------------------

- Uses common OpenAPI client in communications between workflow engines and job
  controller.
- Improves AMQP re-connection handling.
- Enhances test suite and increases code coverage.
- Changes license to MIT.

Version 0.3.0 (2018-09-27)
--------------------------

- Introduces new Serial workflow engine for simple sequential workflow needs.
- Enhances progress reporting for CWL, Serial and Yadage workflow engines.
- Simplifies ``reana-client`` command set and usage scenarios.
- Introduces multi-user capabilities with mandatory access tokens.
- Adds support for multi-node clusters using shared CephFS volumes.
- Adds support for Kubernetes 1.11, Minikube 0.28.2.
- Upgrades CWL workflow engine to use latest ``cwltool`` version.
- Fixes several bugs such as binary file download with Python 3.

Version 0.2.0 (2018-04-23)
--------------------------

- Adds support for Common Workflow Language workflows.
- Adds support for persistent user-selected workflow names.
- Enables file and directory input uploading using absolute paths.
- Enriches ``reana-client`` and ``reana-cluster`` command set.
- Reduces verbosity level for commands and improves error messages.

Version 0.1.0 (2018-01-30)
--------------------------

- Initial public release.

.. admonition:: Please beware

   Please note that REANA is in an early alpha stage of its development. The
   developer preview releases are meant for early adopters and testers. Please
   don't rely on released versions for any production purposes yet.
