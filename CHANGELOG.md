<!-- markdownlint-disable MD013 -->

# Changelog

## [0.95.0](https://github.com/reanahub/reana/compare/0.9.4...0.95.0) (2025-02-24)


### Features

* **helm:** allow configuring number of threads for Dask workers ([#877](https://github.com/reanahub/reana/issues/877)) ([3e3dc24](https://github.com/reanahub/reana/commit/3e3dc24646f94f6b4ba83346e979938c83e1a0fe)), closes [#874](https://github.com/reanahub/reana/issues/874)
* **helm:** allow only reana-server to connect to reana-cache ([#847](https://github.com/reanahub/reana/issues/847)) ([d9c375f](https://github.com/reanahub/reana/commit/d9c375fb479829a557f1828a6fcbd30f5a533e26))
* **helm:** collect logs from Dask pods ([#850](https://github.com/reanahub/reana/issues/850)) ([06fa887](https://github.com/reanahub/reana/commit/06fa887e1e8aa3c99058ae4c5a6c6491337cefa2))
* **helm:** introduce `traefik.external` Helm chart value ([#866](https://github.com/reanahub/reana/issues/866)) ([b2074bc](https://github.com/reanahub/reana/commit/b2074bc7b261ec7aa7eefc40590b6dd94905cc8c)), closes [#852](https://github.com/reanahub/reana/issues/852)
* **helm:** release check on most-supported Kubernetes version ([#848](https://github.com/reanahub/reana/issues/848)) ([d9c375f](https://github.com/reanahub/reana/commit/d9c375fb479829a557f1828a6fcbd30f5a533e26))
* **helm:** support password-protected rabbitmq ([#847](https://github.com/reanahub/reana/issues/847)) ([d9c375f](https://github.com/reanahub/reana/commit/d9c375fb479829a557f1828a6fcbd30f5a533e26))
* **helm:** support password-protected redis ([#847](https://github.com/reanahub/reana/issues/847)) ([d9c375f](https://github.com/reanahub/reana/commit/d9c375fb479829a557f1828a6fcbd30f5a533e26))
* **reana-dev:** add `--namespace` option to `run-ci` command ([#862](https://github.com/reanahub/reana/issues/862)) ([51c3a11](https://github.com/reanahub/reana/commit/51c3a112c0afd1adeb6f004e986369990630ff5f))
* **scripts:** upgrade to Jupyter SciPy 7.2.2 notebook ([#846](https://github.com/reanahub/reana/issues/846)) ([d9c375f](https://github.com/reanahub/reana/commit/d9c375fb479829a557f1828a6fcbd30f5a533e26))


### Bug fixes

* **helm:** allow interactive-session-cleanup job to access RWC ([#853](https://github.com/reanahub/reana/issues/853)) ([d9c375f](https://github.com/reanahub/reana/commit/d9c375fb479829a557f1828a6fcbd30f5a533e26))
* **helm:** harmonise REANA host name and port configurations ([#867](https://github.com/reanahub/reana/issues/867)) ([8acfb28](https://github.com/reanahub/reana/commit/8acfb287b916602f8f8f1cedf5d112b545c17300)), closes [#865](https://github.com/reanahub/reana/issues/865)
* **reana-dev:** correctly handle missing changelog of components ([#858](https://github.com/reanahub/reana/issues/858)) ([d9c375f](https://github.com/reanahub/reana/commit/d9c375fb479829a557f1828a6fcbd30f5a533e26))
* **reana-dev:** use chore commit scope when bumping dependencies ([#868](https://github.com/reanahub/reana/issues/868)) ([3788789](https://github.com/reanahub/reana/commit/378878948e1fa99e3f2e336cbf5d699753aaa08d))


### Continuous integration

* **helm:** configure target branch name for helm linting ([#863](https://github.com/reanahub/reana/issues/863)) ([e2b6037](https://github.com/reanahub/reana/commit/e2b603726ea37a946d0ec09999645861c9e75ce1))


### Documentation

* **helm:** clarify secrets-related warning in README ([#847](https://github.com/reanahub/reana/issues/847)) ([d9c375f](https://github.com/reanahub/reana/commit/d9c375fb479829a557f1828a6fcbd30f5a533e26))


### Chores

* **master:** release 0.95.0-alpha.1 ([251a172](https://github.com/reanahub/reana/commit/251a172977e0eb666d4335809ef43ca692fcfeab))

## [0.9.4](https://github.com/reanahub/reana/compare/0.9.3...0.9.4) (2024-12-16)

### :sparkles: What's new in REANA 0.9.4

REANA 0.9.4 is a minor update that adds support for using user secrets in
Jupyter notebook sessions, adds support for the Compute4PUNCH infrastructure,
fixes issues with the HTCondor compute backend job dispatch, and improves the
security of the platform.

Please see the [REANA 0.9.4 release blog
post](https://blog.reana.io/posts/2024/reana-0.9.4) for more information.

### :zap: Detailed changelog for REANA 0.9.4 components

#### reana [0.9.4](https://github.com/reanahub/reana/compare/0.9.3...0.9.4) (2024-12-03)

* [Build] **helm:** add support for Kubernetes 1.30 ([#799](https://github.com/reanahub/reana/issues/799)) ([748ca07](https://github.com/reanahub/reana/commit/748ca0769c24286cb32b8bfaf3df0114748cfae0))
* [Build] **helm:** add support for Kubernetes 1.31 ([#822](https://github.com/reanahub/reana/issues/822)) ([7da51d3](https://github.com/reanahub/reana/commit/7da51d3be56b9bf03381c41342fb141cfb36b84b))
* [Features] **config:** add Compute4PUNCH backend ([#780](https://github.com/reanahub/reana/issues/780)) ([c2f490b](https://github.com/reanahub/reana/commit/c2f490b8251ffcebcf53a72ac5f2bcc9ce0190b4))
* [Features] **helm:** allow cluster administrator to configure ingress host ([#804](https://github.com/reanahub/reana/issues/804)) ([1479730](https://github.com/reanahub/reana/commit/14797309ff964b7897e072801c441c4c34532856))
* [Features] **helm:** allow only reana-server to connect to reana-cache ([#847](https://github.com/reanahub/reana/issues/847)) ([e1772ff](https://github.com/reanahub/reana/commit/e1772ffb39d2b1b4c91893f6eda0301edabb105f))
* [Features] **helm:** release check on most-supported Kubernetes version ([#848](https://github.com/reanahub/reana/issues/848)) ([1a98b0a](https://github.com/reanahub/reana/commit/1a98b0ab4d248544a03d83da13a66b399819f713))
* [Features] **helm:** support password-protected rabbitmq ([#847](https://github.com/reanahub/reana/issues/847)) ([20a0ea8](https://github.com/reanahub/reana/commit/20a0ea8fcf854c74a508f0b415c066a9912fbe34))
* [Features] **helm:** support password-protected redis ([#847](https://github.com/reanahub/reana/issues/847)) ([be12076](https://github.com/reanahub/reana/commit/be1207630b9cb6c694139d458cd3ea545747b95f))
* [Features] **scripts:** upgrade to Jupyter SciPy 7.2.2 notebook ([#846](https://github.com/reanahub/reana/issues/846)) ([1ca9dea](https://github.com/reanahub/reana/commit/1ca9deaf1b73e18774019cf1e0cb5cc1fb1c3016))
* [Bug fixes] **helm:** allow interactive-session-cleanup job to access RWC ([#853](https://github.com/reanahub/reana/issues/853)) ([b9bc602](https://github.com/reanahub/reana/commit/b9bc602fc5be2ab717d2c09cb9018b6e5ca8180e))
* [Bug fixes] **reana-dev:** correctly handle missing changelog of components ([#858](https://github.com/reanahub/reana/issues/858)) ([32549d1](https://github.com/reanahub/reana/commit/32549d1f4f1ce06d6be015721d8abc1598dba5b1)), closes [#857](https://github.com/reanahub/reana/issues/857)
* [Continuous integration] **python:** pin setuptools 70 ([#822](https://github.com/reanahub/reana/issues/822)) ([be45c54](https://github.com/reanahub/reana/commit/be45c549c057ea2356b2f6688dd142c68ea11d44))
* [Documentation] **helm:** clarify secrets-related warning in README ([#847](https://github.com/reanahub/reana/issues/847)) ([fab5591](https://github.com/reanahub/reana/commit/fab559187a49c21d368c4863cd0a888ff831c330))

#### reana-client [0.9.4](https://github.com/reanahub/reana-client/compare/0.9.3...0.9.4) (2024-11-29)

* [Build] **docker:** create `reana-client` container image ([#710](https://github.com/reanahub/reana-client/issues/710)) ([2c99c5d](https://github.com/reanahub/reana-client/commit/2c99c5d1bd36e4303885875375085f7d714e8732)), closes [#709](https://github.com/reanahub/reana-client/issues/709)
* [Build] **python:** add support for Python 3.13 ([#736](https://github.com/reanahub/reana-client/issues/736)) ([fd9b944](https://github.com/reanahub/reana-client/commit/fd9b9446d58f21cc6e57b343874d55433532c959))
* [Build] **python:** bump shared REANA packages as of 2024-11-28 ([#736](https://github.com/reanahub/reana-client/issues/736)) ([778df03](https://github.com/reanahub/reana-client/commit/778df037dbeb1340478060e7f913dfff7c0235e5))
* [Continuous integration] **actions:** pin setuptools 70 ([#728](https://github.com/reanahub/reana-client/issues/728)) ([0a4bcc7](https://github.com/reanahub/reana-client/commit/0a4bcc79af33dd00a6a03216be32d10000bb432b))
* [Documentation] **cli:** fix `open` command documentation typo ([#728](https://github.com/reanahub/reana-client/issues/728)) ([c822dd6](https://github.com/reanahub/reana-client/commit/c822dd6570d5474e535be83d0ee4beb44ecee85b))

#### reana-commons [0.9.9](https://github.com/reanahub/reana-commons/compare/0.9.8...0.9.9) (2024-11-28)

* [Build] **python:** add support for Python 3.13 ([#480](https://github.com/reanahub/reana-commons/issues/480)) ([5de7605](https://github.com/reanahub/reana-commons/commit/5de760512a3aa86282a9dc31ac031773ddf49ef6))
* [Features] **schema:** allow Compute4PUNCH backend options ([#445](https://github.com/reanahub/reana-commons/issues/445)) ([0570f4a](https://github.com/reanahub/reana-commons/commit/0570f4ade9135a2d340009d2091c97dfc81a2e60))
* [Bug fixes] **config:** remove hard-coded component host name domain ([#458](https://github.com/reanahub/reana-commons/issues/458)) ([f2faeaa](https://github.com/reanahub/reana-commons/commit/f2faeaa76f42c4484db70766fc1d7a3a122ee38f)), closes [#457](https://github.com/reanahub/reana-commons/issues/457)
* [Continuous integration] **actions:** pin setuptools 70 ([#479](https://github.com/reanahub/reana-commons/issues/479)) ([b80bc70](https://github.com/reanahub/reana-commons/commit/b80bc707fa9311e3e5d00ea71bb17f853845d6bf))

#### reana-db [0.9.5](https://github.com/reanahub/reana-db/compare/0.9.4...0.9.5) (2024-11-26)

* [Features] **cli:** add new `migrate-secret-key` command ([#240](https://github.com/reanahub/reana-db/issues/240)) ([efcbe72](https://github.com/reanahub/reana-db/commit/efcbe724a2797edf94a531a2fd49ae0dc25d29f7))
* [Continuous integration] **actions:** pin setuptools 70 ([#239](https://github.com/reanahub/reana-db/issues/239)) ([3202759](https://github.com/reanahub/reana-db/commit/320275969c64513f695ce59a145088f6222aa594))
* [Continuous integration] **python:** test more Python versions ([#239](https://github.com/reanahub/reana-db/issues/239)) ([e0cba7f](https://github.com/reanahub/reana-db/commit/e0cba7faa97cbf2919c4008ec884ea46ec817cd5))

#### reana-job-controller [0.9.4](https://github.com/reanahub/reana-job-controller/compare/0.9.3...0.9.4) (2024-11-29)

* [Build] **deps:** update reana-auth-vomsproxy to 1.3.0 ([#466](https://github.com/reanahub/reana-job-controller/issues/466)) ([72e9ea1](https://github.com/reanahub/reana-job-controller/commit/72e9ea1442d2b6cf7d466d0701e269fda1e15b22))
* [Build] **docker:** pin setuptools 70 ([#465](https://github.com/reanahub/reana-job-controller/issues/465)) ([c593d9b](https://github.com/reanahub/reana-job-controller/commit/c593d9bc84763f142573396be48c762eefa8f6ec))
* [Build] **python:** bump shared REANA packages as of 2024-11-28 ([#477](https://github.com/reanahub/reana-job-controller/issues/477)) ([9cdd06c](https://github.com/reanahub/reana-job-controller/commit/9cdd06c72faa5ded628b2766113ab37ac06f5868))
* [Features] **backends:** add new Compute4PUNCH backend ([#430](https://github.com/reanahub/reana-job-controller/issues/430)) ([4243252](https://github.com/reanahub/reana-job-controller/commit/42432522c8d9dd5e4ee908a16b1be87046908e08))
* [Bug fixes] **config:** read secret key from env ([#476](https://github.com/reanahub/reana-job-controller/issues/476)) ([1b5aa98](https://github.com/reanahub/reana-job-controller/commit/1b5aa98b0ed76ea614dac1209ba23b366d417d9f))
* [Bug fixes] **config:** update reana-auth-vomsproxy to 1.2.1 to fix WLCG IAM ([#457](https://github.com/reanahub/reana-job-controller/issues/457)) ([132868f](https://github.com/reanahub/reana-job-controller/commit/132868f4824a0f4049febf17c90bea0df838e724))
* [Bug fixes] **htcondorcern:** run provided command in unpacked image ([#474](https://github.com/reanahub/reana-job-controller/issues/474)) ([9cda591](https://github.com/reanahub/reana-job-controller/commit/9cda591affaa1f821409961ec4e379e1bf5fa248)), closes [#471](https://github.com/reanahub/reana-job-controller/issues/471)
* [Bug fixes] **htcondorcern:** support multiline commands ([#474](https://github.com/reanahub/reana-job-controller/issues/474)) ([eb07aa9](https://github.com/reanahub/reana-job-controller/commit/eb07aa9b7b03d38dd47cd004ff8b48440ad45c2a)), closes [#470](https://github.com/reanahub/reana-job-controller/issues/470)
* [Bug fixes] **kubernetes:** avoid privilege escalation in Kubernetes jobs ([#476](https://github.com/reanahub/reana-job-controller/issues/476)) ([389f0ea](https://github.com/reanahub/reana-job-controller/commit/389f0ea9606d4ac5fa24458b7cef39e8ab430c64))

#### reana-server [0.9.4](https://github.com/reanahub/reana-server/compare/0.9.3...0.9.4) (2024-11-29)

* [Build] **python:** bump shared REANA packages as of 2024-11-28 ([#714](https://github.com/reanahub/reana-server/issues/714)) ([94fbf77](https://github.com/reanahub/reana-server/commit/94fbf7766218f4ffaf3f23be64ec6d46be1acb00))
* [Features] **config:** make ACCOUNTS_USERINFO_HEADERS customisable ([#713](https://github.com/reanahub/reana-server/issues/713)) ([8c01d51](https://github.com/reanahub/reana-server/commit/8c01d513c2365f337c26a2211c2ddb82df4186d4))
* [Features] **config:** make APP_DEFAULT_SECURE_HEADERS customisable ([#713](https://github.com/reanahub/reana-server/issues/713)) ([1919358](https://github.com/reanahub/reana-server/commit/1919358cb3b05f09bceff9a904e9607760bc3fb1))
* [Features] **config:** make PROXYFIX_CONFIG customisable ([#713](https://github.com/reanahub/reana-server/issues/713)) ([5b6c276](https://github.com/reanahub/reana-server/commit/5b6c276f57f642cc0965f096fa59875b9599df08))
* [Features] **config:** support password-protected redis ([#713](https://github.com/reanahub/reana-server/issues/713)) ([a2aad8a](https://github.com/reanahub/reana-server/commit/a2aad8ac506b98e5c29d357cec65172b6437cc8f))
* [Features] **ext:** improve error message for db decryption error ([#713](https://github.com/reanahub/reana-server/issues/713)) ([bbab1bf](https://github.com/reanahub/reana-server/commit/bbab1bf7338e9790e2195a02e320df16db1826f6))
* [Bug fixes] **config:** do not set DEBUG programmatically ([#713](https://github.com/reanahub/reana-server/issues/713)) ([c98cbc1](https://github.com/reanahub/reana-server/commit/c98cbc1d15afca9309e4839db543ac19cd2036ce))
* [Bug fixes] **config:** read secret key from env ([#713](https://github.com/reanahub/reana-server/issues/713)) ([6ee6422](https://github.com/reanahub/reana-server/commit/6ee6422d87d38339b359ad7a306575b97f210440))
* [Bug fixes] **get_workflow_specification:** avoid returning null parameters ([#689](https://github.com/reanahub/reana-server/issues/689)) ([46633d6](https://github.com/reanahub/reana-server/commit/46633d6bcc151c73880f9ecbd2c02d2246492794))
* [Bug fixes] **reana-admin:** respect service domain when cleaning sessions ([#687](https://github.com/reanahub/reana-server/issues/687)) ([ede882d](https://github.com/reanahub/reana-server/commit/ede882d384ae0959eb8a9484b7d491baa628a1ee))
* [Bug fixes] **set_workflow_status:** publish workflows to submission queue ([#691](https://github.com/reanahub/reana-server/issues/691)) ([6e35bd7](https://github.com/reanahub/reana-server/commit/6e35bd776e17c1bc04145c68c1f5ea3ce5143b7e)), closes [#690](https://github.com/reanahub/reana-server/issues/690)
* [Bug fixes] **start:** validate endpoint parameters ([#689](https://github.com/reanahub/reana-server/issues/689)) ([d2d3673](https://github.com/reanahub/reana-server/commit/d2d3673dac8917d746ddafd84bb3660e7f83c9b6))
* [Continuous integration] **commitlint:** improve checking of merge commits ([#689](https://github.com/reanahub/reana-server/issues/689)) ([69f45fc](https://github.com/reanahub/reana-server/commit/69f45fc3aae9bc625ed733de9af13eb7c0111048))

#### reana-workflow-controller [0.9.4](https://github.com/reanahub/reana-workflow-controller/compare/0.9.3...0.9.4) (2024-11-29)

* [Build] **docker:** pin setuptools 70 ([#601](https://github.com/reanahub/reana-workflow-controller/issues/601)) ([be6a388](https://github.com/reanahub/reana-workflow-controller/commit/be6a3885f4f2e84ca77c7e09a89e5f2f06185452))
* [Build] **python:** bump shared REANA packages as of 2024-11-28 ([#620](https://github.com/reanahub/reana-workflow-controller/issues/620)) ([179fa89](https://github.com/reanahub/reana-workflow-controller/commit/179fa89ccc4a5e77fca9efa403f4ad2003b40db3))
* [Features] **config:** upgrade to Jupyter SciPy 7.2.2 notebook ([#614](https://github.com/reanahub/reana-workflow-controller/issues/614)) ([72f0c4c](https://github.com/reanahub/reana-workflow-controller/commit/72f0c4c69759c8abf1d67c735232e5b6c033d504))
* [Features] **helm:** allow cluster administrator to configure ingress host ([#588](https://github.com/reanahub/reana-workflow-controller/issues/588)) ([a7c9c85](https://github.com/reanahub/reana-workflow-controller/commit/a7c9c851277f3ca191c073fdc6c6d5d4149a95e8))
* [Features] **sessions:** expose user secrets in interactive sessions ([#591](https://github.com/reanahub/reana-workflow-controller/issues/591)) ([784efee](https://github.com/reanahub/reana-workflow-controller/commit/784efee4be8b4a9785d03d3d05b00f3da2b455c2))
* [Bug fixes] **config:** read secret key from env ([#615](https://github.com/reanahub/reana-workflow-controller/issues/615)) ([7df1279](https://github.com/reanahub/reana-workflow-controller/commit/7df1279f45e0981a06c3af705873c4d1d797404d))
* [Bug fixes] **manager:** avoid privilege escalation in Kubernetes jobs ([#615](https://github.com/reanahub/reana-workflow-controller/issues/615)) ([24563e5](https://github.com/reanahub/reana-workflow-controller/commit/24563e568044e29d4399f78d8c081d144f116761))
* [Bug fixes] **manager:** pass RabbitMQ connection details to workflow engine ([#615](https://github.com/reanahub/reana-workflow-controller/issues/615)) ([cf4ee73](https://github.com/reanahub/reana-workflow-controller/commit/cf4ee734788da33f15a80e1fc1f0b3233ea5a007))
* [Bug fixes] **set_workflow_status:** validate endpoint arguments ([#589](https://github.com/reanahub/reana-workflow-controller/issues/589)) ([5945d7f](https://github.com/reanahub/reana-workflow-controller/commit/5945d7fca095531b3601e551c527457f9413643c))

#### reana-workflow-engine-cwl [0.9.4](https://github.com/reanahub/reana-workflow-engine-cwl/compare/0.9.3...0.9.4) (2024-11-29)

* [Build] **docker:** pin setuptools 70 ([#287](https://github.com/reanahub/reana-workflow-engine-cwl/issues/287)) ([3c2cd8a](https://github.com/reanahub/reana-workflow-engine-cwl/commit/3c2cd8a474d167574bf8746b6430f4ae13a83e61))
* [Build] **python:** bump shared REANA packages as of 2024-11-28 ([#289](https://github.com/reanahub/reana-workflow-engine-cwl/issues/289)) ([f9d3688](https://github.com/reanahub/reana-workflow-engine-cwl/commit/f9d3688858e6f1ff52fa58fecd9ce233dd97b0e1))
* [Features] **task:** allow Compute4PUNCH backend options ([#277](https://github.com/reanahub/reana-workflow-engine-cwl/issues/277)) ([9b2a3d0](https://github.com/reanahub/reana-workflow-engine-cwl/commit/9b2a3d0872329e79d0b2d9a0972b0c09f08ff694))

#### reana-workflow-engine-serial [0.9.4](https://github.com/reanahub/reana-workflow-engine-serial/compare/0.9.3...0.9.4) (2024-11-29)

* [Build] **docker:** pin setuptools 70 ([#216](https://github.com/reanahub/reana-workflow-engine-serial/issues/216)) ([f94d003](https://github.com/reanahub/reana-workflow-engine-serial/commit/f94d0036ded9562155528d52f33110e43c954384))
* [Build] **python:** bump shared REANA packages as of 2024-11-28 ([#218](https://github.com/reanahub/reana-workflow-engine-serial/issues/218)) ([430fd04](https://github.com/reanahub/reana-workflow-engine-serial/commit/430fd04acb6485754a0cc5fa4dbeefd3aaa022e4))
* [Features] **tasks:** allow Compute4PUNCH backend options ([#210](https://github.com/reanahub/reana-workflow-engine-serial/issues/210)) ([a6313f2](https://github.com/reanahub/reana-workflow-engine-serial/commit/a6313f22dcdcab08a84b3dd6c8ce7386122d7400))

#### reana-workflow-engine-snakemake [0.9.4](https://github.com/reanahub/reana-workflow-engine-snakemake/compare/0.9.3...0.9.4) (2024-11-29)

* [Build] **docker:** fix XRootD repository location ([#95](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/95)) ([69fea32](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/69fea329dd9bf91ff9eb1de9ac741262512a872a))
* [Build] **docker:** pin setuptools 70 ([#102](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/102)) ([b27c9cf](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/b27c9cfa21603ecc1554931f23c945d3f9e256d6))
* [Build] **python:** bump shared REANA packages as of 2024-11-28 ([#104](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/104)) ([fb9efc8](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/fb9efc8267c24ce65e8d188a5171d8abd5531cd7))
* [Features] **executor:** allow Compute4PUNCH backend options ([#97](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/97)) ([4b00c52](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/4b00c523eb8750f49262471a43c9deefad1021d3))
* [Bug fixes] **executor:** override default resources to remove mem/disk ([#91](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/91)) ([572a83f](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/572a83f5190c7cae95a4607b792f4b6e0c39262c)), closes [#90](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/90)

#### reana-workflow-engine-yadage [0.9.5](https://github.com/reanahub/reana-workflow-engine-yadage/compare/0.9.4...0.9.5) (2024-11-29)

* [Build] **docker:** pin setuptools 70 ([#274](https://github.com/reanahub/reana-workflow-engine-yadage/issues/274)) ([bc505d8](https://github.com/reanahub/reana-workflow-engine-yadage/commit/bc505d84a4092610e883e766ad08d2efefe8d908))
* [Build] **python:** bump shared REANA packages as of 2024-11-28 ([#276](https://github.com/reanahub/reana-workflow-engine-yadage/issues/276)) ([5911143](https://github.com/reanahub/reana-workflow-engine-yadage/commit/59111432c2c5a7fea98a71ffb2d78a9e7c1a47af))
* [Features] **externalbackend:** allow Compute4PUNCH backend options ([#269](https://github.com/reanahub/reana-workflow-engine-yadage/issues/269)) ([1ce8e6a](https://github.com/reanahub/reana-workflow-engine-yadage/commit/1ce8e6a41f14996c50c53fcd7e84565626756ace))

## [0.9.3](https://github.com/reanahub/reana/compare/0.9.2...0.9.3) (2024-03-13)

### :sparkles: What's new in REANA 0.9.3

REANA 0.9.3 is a minor update that upgrades Snakemake workflow engine to
version 7, improves job submission performance for massively-parallel
workflows, improves the clean-up processing for stopped and failed workflows,
and brings other minor improvements and bug fixes.

Please see the [REANA 0.9.3 release blog
post](https://blog.reana.io/posts/2024/reana-0.9.3) for more information.

### :zap: Detailed changelog for REANA 0.9.3 components

#### reana [0.9.3](https://github.com/reanahub/reana/compare/0.9.2...0.9.3) (2024-03-13)

* [Build] **helm:** add support for Kubernetes 1.29 ([#775](https://github.com/reanahub/reana/issues/775)) ([ae90500](https://github.com/reanahub/reana/commit/ae90500acbc101913df1e0b25aa3f2d48de997f0))
* [Features] **helm:** add value to customise env vars of job controller ([#781](https://github.com/reanahub/reana/issues/781)) ([634691f](https://github.com/reanahub/reana/commit/634691fd32cfb08d59eafbae66f23ebc384ca84b))
* [Features] **helm:** add value to customise PostgreSQL docker image ([#774](https://github.com/reanahub/reana/issues/774)) ([07a191f](https://github.com/reanahub/reana/commit/07a191f19c60ac5d11cf1373ef8feaa16b80f0ee)), closes [#773](https://github.com/reanahub/reana/issues/773)
* [Features] **helm:** add value to customise URL of privacy notice ([#778](https://github.com/reanahub/reana/issues/778)) ([650ddbd](https://github.com/reanahub/reana/commit/650ddbd32441251e3d2ff64d8fce463dedb24e51))
* [Features] **helm:** add values to customise env vars of workflow engines ([#781](https://github.com/reanahub/reana/issues/781)) ([35ee032](https://github.com/reanahub/reana/commit/35ee032da142916b4c966b2a2077a720a5710664))
* [Features] **helm:** use PostgreSQL 14.10 in local dev deployment ([#774](https://github.com/reanahub/reana/issues/774)) ([43ead8a](https://github.com/reanahub/reana/commit/43ead8ab3d2167458ffa590259b614ade233e853)), closes [#744](https://github.com/reanahub/reana/issues/744)
* [Features] **reana-dev:** add `git-aggregate-changelog` ([#789](https://github.com/reanahub/reana/issues/789)) ([6210b11](https://github.com/reanahub/reana/commit/6210b1113e5ad03dc71b604a7d7e9834cfe0fa5d))
* [Features] **reana-dev:** add date to commits bumping dependencies ([#787](https://github.com/reanahub/reana/issues/787)) ([a4cb84c](https://github.com/reanahub/reana/commit/a4cb84cf5967658365f4963fd7da179747bb764e))
* [Bug fixes] **reana-dev:** add PR number in commits bumping shared modules ([#783](https://github.com/reanahub/reana/issues/783)) ([57c6755](https://github.com/reanahub/reana/commit/57c67555e7e2055baeb2ebb6cd7bb0e4ba632a2c))
* [Bug fixes] **reana-dev:** create commits that conform to conventional style ([#777](https://github.com/reanahub/reana/issues/777)) ([86d0133](https://github.com/reanahub/reana/commit/86d01331877212baf2081dbddc37f3de20983b56))
* [Bug fixes] **reana-dev:** delete extra files with git-submodule --update ([#764](https://github.com/reanahub/reana/issues/764)) ([e5680ce](https://github.com/reanahub/reana/commit/e5680ce8bd1a9f80dde4ca448f9fc8d21aa1c6ca))
* [Bug fixes] **reana-dev:** detect number of already open PR in commit suffix ([#783](https://github.com/reanahub/reana/issues/783)) ([c533c34](https://github.com/reanahub/reana/commit/c533c34c85360cec0646f4318b1e6653407f6703))
* [Bug fixes] **reana-dev:** update container image labels when releasing ([#765](https://github.com/reanahub/reana/issues/765)) ([fe6bc2c](https://github.com/reanahub/reana/commit/fe6bc2c397e4af2d873761001bfe485e819211be))
* [Code refactoring] **docs:** move from reST to Markdown ([#776](https://github.com/reanahub/reana/issues/776)) ([79aedb9](https://github.com/reanahub/reana/commit/79aedb9ef2ba0c8a933fe2cac334bd51cd32dd85))
* [Code style] **black:** format with black v24 ([#772](https://github.com/reanahub/reana/issues/772)) ([311e157](https://github.com/reanahub/reana/commit/311e1573867b74d722e04835268d5686e5f64f15))
* [Continuous integration] **commitlint:** addition of commit message linter ([#767](https://github.com/reanahub/reana/issues/767)) ([be77666](https://github.com/reanahub/reana/commit/be77666bb80601c0211674a59a3f91d2609712f9))
* [Continuous integration] **commitlint:** allow release commit style ([#785](https://github.com/reanahub/reana/issues/785)) ([a6f95ac](https://github.com/reanahub/reana/commit/a6f95aca9ca1b3fb1663ee2fa7d876ff0da2bf02))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#771](https://github.com/reanahub/reana/issues/771)) ([2c34634](https://github.com/reanahub/reana/commit/2c34634465723d1b9aa3858ce3898625f4ba572f))
* [Continuous integration] **release-please:** initial configuration ([#767](https://github.com/reanahub/reana/issues/767)) ([bb45539](https://github.com/reanahub/reana/commit/bb455393ac1b4d149cfef4df6e96ae730c25501c))
* [Continuous integration] **release-please:** update version in Helm Chart ([#770](https://github.com/reanahub/reana/issues/770)) ([09c9210](https://github.com/reanahub/reana/commit/09c9210d68e29d094c0e76a4002b17a21fcda701))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#771](https://github.com/reanahub/reana/issues/771)) ([035d51c](https://github.com/reanahub/reana/commit/035d51ca95dbab1c225316667ea2d199d924c851))
* [Documentation] **authors:** complete list of contributors ([#779](https://github.com/reanahub/reana/issues/779)) ([123eae8](https://github.com/reanahub/reana/commit/123eae8d4d97846f895ba652bdf30df35dcd7c00))
* [Documentation] **chat:** remove Gitter ([#782](https://github.com/reanahub/reana/issues/782)) ([aba8ac2](https://github.com/reanahub/reana/commit/aba8ac2ae1b5cee0a8970edb2c85453657deb159))

#### reana-client [0.9.3](https://github.com/reanahub/reana-client/compare/0.9.2...0.9.3) (2024-03-13)

* [Build] **appimage:** upgrade to Python 3.8.18 ([#704](https://github.com/reanahub/reana-client/issues/704)) ([783c17a](https://github.com/reanahub/reana-client/commit/783c17a97c265d0d3cfe97857dc414c6bd7c8b11))
* [Bug fixes] **status:** display correct duration of stopped workflows ([#701](https://github.com/reanahub/reana-client/issues/701)) ([b53def8](https://github.com/reanahub/reana-client/commit/b53def8dd3246b10d4da0f2367710af0911e284c)), closes [#699](https://github.com/reanahub/reana-client/issues/699)
* [Code refactoring] **docs:** move from reST to Markdown ([#703](https://github.com/reanahub/reana-client/issues/703)) ([c9c4d53](https://github.com/reanahub/reana-client/commit/c9c4d530eb3e1e3d6996fe71821116815c8eaba3))
* [Code style] **black:** format with black v24 ([#702](https://github.com/reanahub/reana-client/issues/702)) ([02dc830](https://github.com/reanahub/reana-client/commit/02dc83009a6477c1ae045f4e1a6ea9f9e66640fb))
* [Test suite] **snakemake:** allow running Snakemake 7 tests on Python 3.11+ ([#700](https://github.com/reanahub/reana-client/issues/700)) ([8ad7ff1](https://github.com/reanahub/reana-client/commit/8ad7ff19e98d1f9231af65bf608d408031546a3e)), closes [#655](https://github.com/reanahub/reana-client/issues/655)
* [Continuous integration] **commitlint:** addition of commit message linter ([#695](https://github.com/reanahub/reana-client/issues/695)) ([2de7d61](https://github.com/reanahub/reana-client/commit/2de7d61db96693e8ee9c3ac555aef9dbfd7bb4bc))
* [Continuous integration] **commitlint:** allow release commit style ([#708](https://github.com/reanahub/reana-client/issues/708)) ([f552752](https://github.com/reanahub/reana-client/commit/f55275296cd6cc72b4d21d89f51442842cb15d30))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#698](https://github.com/reanahub/reana-client/issues/698)) ([fa5b7c7](https://github.com/reanahub/reana-client/commit/fa5b7c76eb25bfb1591e6fae4a142d975e14b937))
* [Continuous integration] **pytest:** install `tests` package variant instead of `all` ([#703](https://github.com/reanahub/reana-client/issues/703)) ([fe0b00a](https://github.com/reanahub/reana-client/commit/fe0b00af1ad7b79ec607de7b810f597a3d6df93a))
* [Continuous integration] **release-please:** initial configuration ([#695](https://github.com/reanahub/reana-client/issues/695)) ([5b278f1](https://github.com/reanahub/reana-client/commit/5b278f131b59d3ecfd3c7f129040a126cd01b60a))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#698](https://github.com/reanahub/reana-client/issues/698)) ([fe696ea](https://github.com/reanahub/reana-client/commit/fe696eae4cef119b29784ab80ec03d3f4cc089ea))
* [Documentation] **authors:** complete list of contributors ([#705](https://github.com/reanahub/reana-client/issues/705)) ([875997c](https://github.com/reanahub/reana-client/commit/875997c06e657d3e19e1af32324127caa2b1a9c5))

#### reana-commons [0.9.8](https://github.com/reanahub/reana-commons/compare/0.9.7...0.9.8) (2024-03-01)

* [Build] **python:** change extra names to comply with PEP 685 ([#446](https://github.com/reanahub/reana-commons/issues/446)) ([9dad6da](https://github.com/reanahub/reana-commons/commit/9dad6da7b80bc07423d45dab7b6799911740a082))
* [Build] **python:** require smart-open&lt;7 for Python 3.6 ([#446](https://github.com/reanahub/reana-commons/issues/446)) ([17fd581](https://github.com/reanahub/reana-commons/commit/17fd581d4928d5c377f67bcb77c4f245e661c395))
* [Build] **python:** restore snakemake `reports` extra ([#446](https://github.com/reanahub/reana-commons/issues/446)) ([904178f](https://github.com/reanahub/reana-commons/commit/904178fe454b9af39164a0c327f1ecd1663132af))
* [Continuous integration] **commitlint:** allow release commit style ([#447](https://github.com/reanahub/reana-commons/issues/447)) ([1208ccf](https://github.com/reanahub/reana-commons/commit/1208ccf2de844afe788d7bbccbd4f63b24af427e))

#### reana-commons [0.9.7](https://github.com/reanahub/reana-commons/compare/0.9.6...0.9.7) (2024-02-20)

* [Build] **snakemake:** require pulp&lt;2.8.0 ([#444](https://github.com/reanahub/reana-commons/issues/444)) ([5daa109](https://github.com/reanahub/reana-commons/commit/5daa109a58066126c2d8a35e7cd7da70d4137f62))
* [Documentation] **authors:** complete list of contributors ([#442](https://github.com/reanahub/reana-commons/issues/442)) ([4a74c10](https://github.com/reanahub/reana-commons/commit/4a74c10e7a248f580778ebc772bffe94e533e7ed))

#### reana-commons [0.9.6](https://github.com/reanahub/reana-commons/compare/0.9.5...0.9.6) (2024-02-13)

* [Features] **config:** allow customisation of runtime group name ([#440](https://github.com/reanahub/reana-commons/issues/440)) ([5cec305](https://github.com/reanahub/reana-commons/commit/5cec30561ba21e2ea695e20eaea8171226f06e52))
* [Features] **snakemake:** upgrade to Snakemake 7.32.4 ([#435](https://github.com/reanahub/reana-commons/issues/435)) ([20ae9ce](https://github.com/reanahub/reana-commons/commit/20ae9cebf19a1fdb77ad08956db04ef026521b5d))
* [Bug fixes] **cache:** handle deleted files when calculating access times ([#437](https://github.com/reanahub/reana-commons/issues/437)) ([698900f](https://github.com/reanahub/reana-commons/commit/698900fc63e20bd54dcc4a5faa6cac0be5d0d8de))
* [Code refactoring] **docs:** move from reST to Markdown ([#441](https://github.com/reanahub/reana-commons/issues/441)) ([36ce4e0](https://github.com/reanahub/reana-commons/commit/36ce4e0a86484e3a7006e20545a892424ce0f3a2))
* [Continuous integration] **commitlint:** addition of commit message linter ([#432](https://github.com/reanahub/reana-commons/issues/432)) ([a67906f](https://github.com/reanahub/reana-commons/commit/a67906fe8620e1f624e24e8a4511694a9b60378d))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#438](https://github.com/reanahub/reana-commons/issues/438)) ([d3035dc](https://github.com/reanahub/reana-commons/commit/d3035dc12cecf16edcbec462dfdb1386da16f6d6))
* [Continuous integration] **release-please:** initial configuration ([#432](https://github.com/reanahub/reana-commons/issues/432)) ([687f2f4](https://github.com/reanahub/reana-commons/commit/687f2f4ea8c5c49a70c6f121faf7e59a98dd3138))
* [Continuous integration] **shellcheck:** check all shell scripts recursively ([#436](https://github.com/reanahub/reana-commons/issues/436)) ([709a685](https://github.com/reanahub/reana-commons/commit/709a685b3a8586b069a98c0338283a6bd2721005))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#438](https://github.com/reanahub/reana-commons/issues/438)) ([85d9a2a](https://github.com/reanahub/reana-commons/commit/85d9a2a68e3929f442e03d5422a37ffd6b7169c6))

#### reana-commons 0.9.5 (2023-12-15)

* Fixes installation by pinning `bravado-core` to versions lower than 6.1.1.

#### reana-db [0.9.4](https://github.com/reanahub/reana-db/compare/0.9.3...0.9.4) (2024-03-01)

* [Code refactoring] **docs:** move from reST to Markdown ([#225](https://github.com/reanahub/reana-db/issues/225)) ([b48eb55](https://github.com/reanahub/reana-db/commit/b48eb55f7a1b1bbdde0e0a458852349a439a511e))
* [Code style] **black:** format with black v24 ([#224](https://github.com/reanahub/reana-db/issues/224)) ([cc60522](https://github.com/reanahub/reana-db/commit/cc6052242fd14cf3413b793d0aa32a24871fe1b1))
* [Continuous integration] **commitlint:** addition of commit message linter ([#218](https://github.com/reanahub/reana-db/issues/218)) ([ee0f7e5](https://github.com/reanahub/reana-db/commit/ee0f7e5e106e0be619779bfa2133415feecc323b))
* [Continuous integration] **commitlint:** allow release commit style ([#229](https://github.com/reanahub/reana-db/issues/229)) ([adf15d7](https://github.com/reanahub/reana-db/commit/adf15d7c6457eddadc3da1aa8b95b74cfc1239fb))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#223](https://github.com/reanahub/reana-db/issues/223)) ([3d513f6](https://github.com/reanahub/reana-db/commit/3d513f6cda44e9e40b3c8f3967fcb87d113287ec))
* [Continuous integration] **pytest:** move to PostgreSQL 14.10 ([#226](https://github.com/reanahub/reana-db/issues/226)) ([4dac889](https://github.com/reanahub/reana-db/commit/4dac88953754c0810d3502e8e511ec90c27c2b43))
* [Continuous integration] **release-please:** initial configuration ([#218](https://github.com/reanahub/reana-db/issues/218)) ([7c616d6](https://github.com/reanahub/reana-db/commit/7c616d67fac642656f56d37422ba69c4a8d4fa20))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#223](https://github.com/reanahub/reana-db/issues/223)) ([b62ee1e](https://github.com/reanahub/reana-db/commit/b62ee1e3be44628265bf5ada7e0b7eb88e283c00))
* [Documentation] **authors:** complete list of contributors ([#227](https://github.com/reanahub/reana-db/issues/227)) ([3fbcf65](https://github.com/reanahub/reana-db/commit/3fbcf65db735146d54078cae4c5b9c8968ead055))

#### reana-job-controller [0.9.3](https://github.com/reanahub/reana-job-controller/compare/0.9.2...0.9.3) (2024-03-04)

* [Build] **certificates:** update expired CERN Grid CA certificate ([#440](https://github.com/reanahub/reana-job-controller/issues/440)) ([8d6539a](https://github.com/reanahub/reana-job-controller/commit/8d6539a94af035aca1191c9a6a7ff43791a3c930)), closes [#439](https://github.com/reanahub/reana-job-controller/issues/439)
* [Build] **docker:** non-editable submodules in "latest" mode ([#416](https://github.com/reanahub/reana-job-controller/issues/416)) ([3bdda63](https://github.com/reanahub/reana-job-controller/commit/3bdda6367d9a4682028a2a7df7268e4c9b42ef6c))
* [Build] **python:** bump all required packages as of 2024-03-04 ([#442](https://github.com/reanahub/reana-job-controller/issues/442)) ([de119eb](https://github.com/reanahub/reana-job-controller/commit/de119eb8f663dcfe1a126747a7c404e39ece47c0))
* [Build] **python:** bump shared REANA packages as of 2024-03-04 ([#442](https://github.com/reanahub/reana-job-controller/issues/442)) ([fc77628](https://github.com/reanahub/reana-job-controller/commit/fc776284abe15030581d5adf4aa575f4f3a1c756))
* [Features] **shutdown:** stop all running jobs before stopping workflow ([#423](https://github.com/reanahub/reana-job-controller/issues/423)) ([866675b](https://github.com/reanahub/reana-job-controller/commit/866675b7288e840130cfee851f4a248a9ae2617d))
* [Bug fixes] **database:** limit the number of open database connections ([#437](https://github.com/reanahub/reana-job-controller/issues/437)) ([980f749](https://github.com/reanahub/reana-job-controller/commit/980f74982b75176c5958f09bc581e941cdf44310))
* [Performance improvements] **cache:** avoid caching jobs when the cache is disabled ([#435](https://github.com/reanahub/reana-job-controller/issues/435)) ([553468f](https://github.com/reanahub/reana-job-controller/commit/553468f55f6b63cebba45ccd460593131e5dcfea)), closes [#422](https://github.com/reanahub/reana-job-controller/issues/422)
* [Code refactoring] **db:** set job status also in the main database ([#423](https://github.com/reanahub/reana-job-controller/issues/423)) ([9d6fc99](https://github.com/reanahub/reana-job-controller/commit/9d6fc99063deb468fe9d45d9ad626c745c7bd827))
* [Code refactoring] **docs:** move from reST to Markdown ([#428](https://github.com/reanahub/reana-job-controller/issues/428)) ([4732884](https://github.com/reanahub/reana-job-controller/commit/4732884a3da52694fb86d72873eceef3ad2deb27))
* [Code refactoring] **monitor:** centralise logs and status updates ([#423](https://github.com/reanahub/reana-job-controller/issues/423)) ([3685b01](https://github.com/reanahub/reana-job-controller/commit/3685b01a57e1d0b1bd363534ff331b988e04719e))
* [Code refactoring] **monitor:** move fetching of logs to job-manager ([#423](https://github.com/reanahub/reana-job-controller/issues/423)) ([1fc117e](https://github.com/reanahub/reana-job-controller/commit/1fc117ebb3dd908a01ee3fd539fa24a07cdb4d16))
* [Code style] **black:** format with black v24 ([#426](https://github.com/reanahub/reana-job-controller/issues/426)) ([8a2757e](https://github.com/reanahub/reana-job-controller/commit/8a2757ee8bf52d1d5189f1dd1d690cb8922599cb))
* [Continuous integration] **commitlint:** addition of commit message linter ([#417](https://github.com/reanahub/reana-job-controller/issues/417)) ([f547d3b](https://github.com/reanahub/reana-job-controller/commit/f547d3bc25f438203252ea149cf6c6e5d2428189))
* [Continuous integration] **commitlint:** allow release commit style ([#443](https://github.com/reanahub/reana-job-controller/issues/443)) ([0fc9794](https://github.com/reanahub/reana-job-controller/commit/0fc9794bfbe2799bb9666ec5b2ff1dd15def8c34))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#425](https://github.com/reanahub/reana-job-controller/issues/425)) ([35bc1c5](https://github.com/reanahub/reana-job-controller/commit/35bc1c5acb1aa8ff51689142a007da66e49d8d2b))
* [Continuous integration] **pytest:** move to PostgreSQL 14.10 ([#429](https://github.com/reanahub/reana-job-controller/issues/429)) ([42622fa](https://github.com/reanahub/reana-job-controller/commit/42622fa1597e49fae36c625941188be5a093eda9))
* [Continuous integration] **release-please:** initial configuration ([#417](https://github.com/reanahub/reana-job-controller/issues/417)) ([fca6f74](https://github.com/reanahub/reana-job-controller/commit/fca6f74aa0d0e55e41d96b0e79c66a5cb3517189))
* [Continuous integration] **release-please:** update version in Dockerfile/OpenAPI specs ([#421](https://github.com/reanahub/reana-job-controller/issues/421)) ([e6742f2](https://github.com/reanahub/reana-job-controller/commit/e6742f2911df46dfbef3b7e9104330d58e2b4211))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#425](https://github.com/reanahub/reana-job-controller/issues/425)) ([8e74a85](https://github.com/reanahub/reana-job-controller/commit/8e74a85c90df00c8734a6cdd81597f583d11d566))
* [Documentation] **authors:** complete list of contributors ([#434](https://github.com/reanahub/reana-job-controller/issues/434)) ([b9f8364](https://github.com/reanahub/reana-job-controller/commit/b9f83647fa8fc337140da5c3f2814ea24a15c5d5))

#### reana-message-broker [0.9.3](https://github.com/reanahub/reana-message-broker/compare/0.9.2...0.9.3) (2024-03-01)

* [Bug fixes] **startup:** handle signals for graceful shutdown ([#59](https://github.com/reanahub/reana-message-broker/issues/59)) ([abb8969](https://github.com/reanahub/reana-message-broker/commit/abb8969c5fa817fb2db5143df53d89d898225645))
* [Code refactoring] **docs:** move from reST to Markdown ([#65](https://github.com/reanahub/reana-message-broker/issues/65)) ([e5bd869](https://github.com/reanahub/reana-message-broker/commit/e5bd8695a0c4d6184e83eef1fbb410566ffa370d))
* [Continuous integration] **commitlint:** addition of commit message linter ([#60](https://github.com/reanahub/reana-message-broker/issues/60)) ([a9ee4bb](https://github.com/reanahub/reana-message-broker/commit/a9ee4bb308bc8f702a1ea56d62957c218faf72eb))
* [Continuous integration] **commitlint:** allow release commit style ([#67](https://github.com/reanahub/reana-message-broker/issues/67)) ([600aa01](https://github.com/reanahub/reana-message-broker/commit/600aa01dcd3bdc029a49b0f7667edf4953387920))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#64](https://github.com/reanahub/reana-message-broker/issues/64)) ([8283064](https://github.com/reanahub/reana-message-broker/commit/828306458ede34ee77617acb624b73f258235d0e))
* [Continuous integration] **release-please:** initial configuration ([#60](https://github.com/reanahub/reana-message-broker/issues/60)) ([02b3595](https://github.com/reanahub/reana-message-broker/commit/02b35957d01e40f3bf00a6ffc5a40fe3d7f7dde2))
* [Continuous integration] **release-please:** update version in Dockerfile ([#63](https://github.com/reanahub/reana-message-broker/issues/63)) ([548f3e1](https://github.com/reanahub/reana-message-broker/commit/548f3e13f797b733779113b96509126897fbe526))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#64](https://github.com/reanahub/reana-message-broker/issues/64)) ([8a2a7fc](https://github.com/reanahub/reana-message-broker/commit/8a2a7fc6e78d49059e22f9a6b14ac4395e48e600))
* [Documentation] **authors:** complete list of contributors ([#66](https://github.com/reanahub/reana-message-broker/issues/66)) ([56fbc8c](https://github.com/reanahub/reana-message-broker/commit/56fbc8c48acc687dbf7d228b2cfe19a6db50a01f))

#### reana-server [0.9.3](https://github.com/reanahub/reana-server/compare/0.9.2...0.9.3) (2024-03-04)

* [Build] **deps:** pin invenio-userprofiles to 1.2.4 ([#665](https://github.com/reanahub/reana-server/issues/665)) ([d6cb168](https://github.com/reanahub/reana-server/commit/d6cb16854aea78d852ab43987a44933a9d6fbcad))
* [Build] **docker:** non-editable submodules in "latest" mode ([#656](https://github.com/reanahub/reana-server/issues/656)) ([d16fefb](https://github.com/reanahub/reana-server/commit/d16fefb421e1d0cc712006c6a697ea67057b1f6c))
* [Build] **python:** bump all required packages as of 2024-03-04 ([#674](https://github.com/reanahub/reana-server/issues/674)) ([f40b82f](https://github.com/reanahub/reana-server/commit/f40b82f983d295348a4a5a537b4147a9dc8b6dae))
* [Build] **python:** bump shared modules ([#676](https://github.com/reanahub/reana-server/issues/676)) ([47ad3ca](https://github.com/reanahub/reana-server/commit/47ad3caab04119568b0f790075784aae59c3818d))
* [Build] **python:** bump shared REANA packages as of 2024-03-04 ([#674](https://github.com/reanahub/reana-server/issues/674)) ([aa18394](https://github.com/reanahub/reana-server/commit/aa18394458d56806913e224e1b6651a177d18b39))
* [Code refactoring] **docs:** move from reST to Markdown ([#671](https://github.com/reanahub/reana-server/issues/671)) ([b6d1799](https://github.com/reanahub/reana-server/commit/b6d1799552085e1a9c2ad53eafcd572f1af4f3bf))
* [Code style] **black:** format with black v24 ([#670](https://github.com/reanahub/reana-server/issues/670)) ([6d2b898](https://github.com/reanahub/reana-server/commit/6d2b898b2322e6677739fdb1c3bd3916a3cf0887))
* [Continuous integration] **commitlint:** addition of commit message linter ([#665](https://github.com/reanahub/reana-server/issues/665)) ([2b43ecc](https://github.com/reanahub/reana-server/commit/2b43eccdd7587970f92093b4d315a7a90b5f45ac))
* [Continuous integration] **commitlint:** allow release commit style ([#675](https://github.com/reanahub/reana-server/issues/675)) ([e0299ef](https://github.com/reanahub/reana-server/commit/e0299efb273f2c95f88f86261c97a4bc6100786d))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#669](https://github.com/reanahub/reana-server/issues/669)) ([87c6145](https://github.com/reanahub/reana-server/commit/87c6145e636d852ba5fd5ca6fa2cfc23ff6563d2))
* [Continuous integration] **pytest:** move to PostgreSQL 14.10 ([#672](https://github.com/reanahub/reana-server/issues/672)) ([e888ddd](https://github.com/reanahub/reana-server/commit/e888ddd70d8ca17d4567c24b7d78a57bf6f8e060))
* [Continuous integration] **release-please:** initial configuration ([#665](https://github.com/reanahub/reana-server/issues/665)) ([1d5e7c5](https://github.com/reanahub/reana-server/commit/1d5e7c5f4c3d471d0b2028274ec1785b53552d89))
* [Continuous integration] **release-please:** update version in Dockerfile/OpenAPI specs ([#668](https://github.com/reanahub/reana-server/issues/668)) ([3b3dc41](https://github.com/reanahub/reana-server/commit/3b3dc418f40d5ce461e4a7418178f6a8cec2721f))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#669](https://github.com/reanahub/reana-server/issues/669)) ([d7eac6b](https://github.com/reanahub/reana-server/commit/d7eac6b26742797cb1b2c7077071fc3d2053aff1))
* [Documentation] **authors:** complete list of contributors ([#673](https://github.com/reanahub/reana-server/issues/673)) ([71b3f38](https://github.com/reanahub/reana-server/commit/71b3f387b0816e23a3315c379ed45af0bb6661a3))

#### reana-ui [0.9.4](https://github.com/reanahub/reana-ui/compare/0.9.3...0.9.4) (2024-03-04)

* [Build] **package:** require jsroot&lt;7.6.0 ([#399](https://github.com/reanahub/reana-ui/issues/399)) ([d53b290](https://github.com/reanahub/reana-ui/commit/d53b290f7264e5da8e7b31c6ef2015748146e2f0))
* [Build] **package:** update yarn.lock ([#399](https://github.com/reanahub/reana-ui/issues/399)) ([10e41b1](https://github.com/reanahub/reana-ui/commit/10e41b17cc45cb43fafa5f755c2730aa6c047933))
* [Features] **footer:** link privacy notice to configured URL ([#393](https://github.com/reanahub/reana-ui/issues/393)) ([f0edde6](https://github.com/reanahub/reana-ui/commit/f0edde6bf4ceb8a92915446d0353df009919b8f3)), closes [#392](https://github.com/reanahub/reana-ui/issues/392)
* [Bug fixes] **launcher:** remove dollar sign in generated Markdown ([#389](https://github.com/reanahub/reana-ui/issues/389)) ([8ad4afd](https://github.com/reanahub/reana-ui/commit/8ad4afdf9053a3736e4df036646aa114260f79d9))
* [Bug fixes] **progress:** update failed workflows duration using finish time ([#387](https://github.com/reanahub/reana-ui/issues/387)) ([809fdc5](https://github.com/reanahub/reana-ui/commit/809fdc5e8b35ef03490921d15febcdb819fa6df7)), closes [#386](https://github.com/reanahub/reana-ui/issues/386)
* [Bug fixes] **router:** show 404 page for invalid URLs ([#382](https://github.com/reanahub/reana-ui/issues/382)) ([c18e81d](https://github.com/reanahub/reana-ui/commit/c18e81ded87db6fbbbf06237d747f9655e0e5cc9)), closes [#379](https://github.com/reanahub/reana-ui/issues/379)
* [Code refactoring] **docs:** move from reST to Markdown ([#391](https://github.com/reanahub/reana-ui/issues/391)) ([8d58277](https://github.com/reanahub/reana-ui/commit/8d582775ab1a0779601e37f9b9498f76cc5ce4cd))
* [Continuous integration] **commitlint:** addition of commit message linter ([#380](https://github.com/reanahub/reana-ui/issues/380)) ([1c9ec74](https://github.com/reanahub/reana-ui/commit/1c9ec7493a28c8c482acb6a90e4c4baf16bf9507))
* [Continuous integration] **commitlint:** allow release commit style ([#400](https://github.com/reanahub/reana-ui/issues/400)) ([426a2b0](https://github.com/reanahub/reana-ui/commit/426a2b0c3c401c52a3ad39fa7d5c5d3834eb2082))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#390](https://github.com/reanahub/reana-ui/issues/390)) ([e938f60](https://github.com/reanahub/reana-ui/commit/e938f60440bb8c48ac8f00637e44d5f34980137e))
* [Continuous integration] **release-please:** initial configuration ([#380](https://github.com/reanahub/reana-ui/issues/380)) ([db2e82b](https://github.com/reanahub/reana-ui/commit/db2e82b454ba80b93895835e7c95ae96f3ff5dc9))
* [Continuous integration] **release-please:** switch to `simple` release strategy ([#383](https://github.com/reanahub/reana-ui/issues/383)) ([2c64085](https://github.com/reanahub/reana-ui/commit/2c64085dd8dc70ceaf775b527f5467ae297e09e5))
* [Continuous integration] **release-please:** update version in package.json and Dockerfile ([#385](https://github.com/reanahub/reana-ui/issues/385)) ([5d232af](https://github.com/reanahub/reana-ui/commit/5d232aff36d1f795df1fc8736ae3825a2b763750))
* [Continuous integration] **shellcheck:** exclude node_modules from the analyzed paths ([#387](https://github.com/reanahub/reana-ui/issues/387)) ([8913e4d](https://github.com/reanahub/reana-ui/commit/8913e4dd58250bf30318539c8f75abda0b024e43))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#390](https://github.com/reanahub/reana-ui/issues/390)) ([7b5f29e](https://github.com/reanahub/reana-ui/commit/7b5f29ebc604a2d27d76f8a51b437c3e561fec32))
* [Documentation] **authors:** complete list of contributors ([#396](https://github.com/reanahub/reana-ui/issues/396)) ([814d68e](https://github.com/reanahub/reana-ui/commit/814d68ef5e2103a5f33e0dcf97bd8ffd777db78f))

#### reana-workflow-controller [0.9.3](https://github.com/reanahub/reana-workflow-controller/compare/0.9.2...0.9.3) (2024-03-04)

* [Build] **docker:** non-editable submodules in "latest" mode ([#551](https://github.com/reanahub/reana-workflow-controller/issues/551)) ([af74d0b](https://github.com/reanahub/reana-workflow-controller/commit/af74d0b887d02109ce96c91ef8fdf99e4eb4ff34))
* [Build] **python:** bump all required packages as of 2024-03-04 ([#574](https://github.com/reanahub/reana-workflow-controller/issues/574)) ([1373f4c](https://github.com/reanahub/reana-workflow-controller/commit/1373f4c3ea9480cc7ccb05ab12fc62a029e1f792))
* [Build] **python:** bump shared REANA packages as of 2024-03-04 ([#574](https://github.com/reanahub/reana-workflow-controller/issues/574)) ([e31d903](https://github.com/reanahub/reana-workflow-controller/commit/e31d9038280a68ff84595caa64f010a4f25fc63a))
* [Features] **manager:** call shutdown endpoint before workflow stop ([#559](https://github.com/reanahub/reana-workflow-controller/issues/559)) ([719fa37](https://github.com/reanahub/reana-workflow-controller/commit/719fa370839dd29ce8071b2d1e203ff37c5ff4f1))
* [Features] **manager:** increase termination period of run-batch pods ([#572](https://github.com/reanahub/reana-workflow-controller/issues/572)) ([f05096a](https://github.com/reanahub/reana-workflow-controller/commit/f05096ac7d5c6e7a535772966ccbbb2e07a325ef))
* [Features] **manager:** pass custom env variables to job controller ([#571](https://github.com/reanahub/reana-workflow-controller/issues/571)) ([646f071](https://github.com/reanahub/reana-workflow-controller/commit/646f071feb61c7b901cc8979b02bc846a3f0a343))
* [Features] **manager:** pass custom env variables to workflow engines ([#571](https://github.com/reanahub/reana-workflow-controller/issues/571)) ([cb9369b](https://github.com/reanahub/reana-workflow-controller/commit/cb9369bb3ca6beb70d0693fef277df1958121169))
* [Bug fixes] **manager:** graceful shutdown of job-controller ([#559](https://github.com/reanahub/reana-workflow-controller/issues/559)) ([817b019](https://github.com/reanahub/reana-workflow-controller/commit/817b019b3745862436e99570c10c6d8ea35533f4))
* [Bug fixes] **manager:** use valid group name when calling `groupadd` ([#566](https://github.com/reanahub/reana-workflow-controller/issues/566)) ([73a9929](https://github.com/reanahub/reana-workflow-controller/commit/73a9929a742e18a482824c2ca9a7c52f1f46227e)), closes [#561](https://github.com/reanahub/reana-workflow-controller/issues/561)
* [Bug fixes] **stop:** store engine logs of stopped workflow ([#563](https://github.com/reanahub/reana-workflow-controller/issues/563)) ([199c163](https://github.com/reanahub/reana-workflow-controller/commit/199c16313d97932f80080585a0c617b6b0e3a78d)), closes [#560](https://github.com/reanahub/reana-workflow-controller/issues/560)
* [Code refactoring] **consumer:** do not update status of jobs ([#559](https://github.com/reanahub/reana-workflow-controller/issues/559)) ([5992034](https://github.com/reanahub/reana-workflow-controller/commit/599203403576784f6efabd158df7282431265cdc))
* [Code refactoring] **docs:** move from reST to Markdown ([#567](https://github.com/reanahub/reana-workflow-controller/issues/567)) ([4fbdb74](https://github.com/reanahub/reana-workflow-controller/commit/4fbdb74a5351155b7e0ac4ac97114a8fa3ec60f5))
* [Code style] **black:** format with black v24 ([#564](https://github.com/reanahub/reana-workflow-controller/issues/564)) ([2329437](https://github.com/reanahub/reana-workflow-controller/commit/23294373b384e19280c00f3116100816e7277e40))
* [Continuous integration] **commitlint:** addition of commit message linter ([#555](https://github.com/reanahub/reana-workflow-controller/issues/555)) ([b9df20a](https://github.com/reanahub/reana-workflow-controller/commit/b9df20a78d36b6fb664fc69127ace5d9cdd73830))
* [Continuous integration] **commitlint:** allow release commit style ([#575](https://github.com/reanahub/reana-workflow-controller/issues/575)) ([b013d49](https://github.com/reanahub/reana-workflow-controller/commit/b013d49e61b372b9ac4f8a9f1e7ceafae64295f1))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#562](https://github.com/reanahub/reana-workflow-controller/issues/562)) ([4b8f539](https://github.com/reanahub/reana-workflow-controller/commit/4b8f53909d281dcd2445833544c4107c8ebd1d81))
* [Continuous integration] **pytest:** move to PostgreSQL 14.10 ([#568](https://github.com/reanahub/reana-workflow-controller/issues/568)) ([9b6bfa0](https://github.com/reanahub/reana-workflow-controller/commit/9b6bfa0b5057d849f8667ee0642765150e2b52d9))
* [Continuous integration] **release-please:** initial configuration ([#555](https://github.com/reanahub/reana-workflow-controller/issues/555)) ([672083d](https://github.com/reanahub/reana-workflow-controller/commit/672083de4c943a1c32b0a093542919b72102b491))
* [Continuous integration] **release-please:** update version in Dockerfile/OpenAPI specs ([#558](https://github.com/reanahub/reana-workflow-controller/issues/558)) ([4be8086](https://github.com/reanahub/reana-workflow-controller/commit/4be8086874b1eb7e355a75ef0e79467b0a9db875))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#562](https://github.com/reanahub/reana-workflow-controller/issues/562)) ([c5d4982](https://github.com/reanahub/reana-workflow-controller/commit/c5d498299f8524f016f4e8c33c9ac0e90b644cb7))
* [Documentation] **authors:** complete list of contributors ([#570](https://github.com/reanahub/reana-workflow-controller/issues/570)) ([08ab9a3](https://github.com/reanahub/reana-workflow-controller/commit/08ab9a3358ee8b027a62e1a528f7e135a676b55a))

#### reana-workflow-engine-cwl [0.9.3](https://github.com/reanahub/reana-workflow-engine-cwl/compare/0.9.2...0.9.3) (2024-03-04)

* [Build] **docker:** install correct extras of reana-commons submodule ([#261](https://github.com/reanahub/reana-workflow-engine-cwl/issues/261)) ([21957fe](https://github.com/reanahub/reana-workflow-engine-cwl/commit/21957fe41921d9c557067b2773205af6385f755b))
* [Build] **docker:** non-editable submodules in "latest" mode ([#255](https://github.com/reanahub/reana-workflow-engine-cwl/issues/255)) ([a6acc88](https://github.com/reanahub/reana-workflow-engine-cwl/commit/a6acc888a36694e3306993cfc3108752b60bd1f3))
* [Build] **python:** bump all required packages as of 2024-03-04 ([#267](https://github.com/reanahub/reana-workflow-engine-cwl/issues/267)) ([ed6a846](https://github.com/reanahub/reana-workflow-engine-cwl/commit/ed6a846eb1d8a0bf92f77906749b5853e5794114))
* [Build] **python:** bump shared REANA packages as of 2024-03-04 ([#267](https://github.com/reanahub/reana-workflow-engine-cwl/issues/267)) ([47155ef](https://github.com/reanahub/reana-workflow-engine-cwl/commit/47155ef95c4eb19642dd54a732402b2551973658))
* [Bug fixes] **progress:** handle stopped jobs ([#260](https://github.com/reanahub/reana-workflow-engine-cwl/issues/260)) ([bc36cb7](https://github.com/reanahub/reana-workflow-engine-cwl/commit/bc36cb7813a20fde685a40694af0732ded483d3a))
* [Code refactoring] **docs:** move from reST to Markdown ([#263](https://github.com/reanahub/reana-workflow-engine-cwl/issues/263)) ([3cf272f](https://github.com/reanahub/reana-workflow-engine-cwl/commit/3cf272f657cc3e0b329c6d159f5e476f06000f93))
* [Continuous integration] **commitlint:** addition of commit message linter ([#256](https://github.com/reanahub/reana-workflow-engine-cwl/issues/256)) ([021854e](https://github.com/reanahub/reana-workflow-engine-cwl/commit/021854e309999938cf01c31bda5ab095679e03b0))
* [Continuous integration] **commitlint:** allow release commit style ([#268](https://github.com/reanahub/reana-workflow-engine-cwl/issues/268)) ([ed7ad11](https://github.com/reanahub/reana-workflow-engine-cwl/commit/ed7ad114ccf09ab3182b4cdd49265761f44cd37b))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#262](https://github.com/reanahub/reana-workflow-engine-cwl/issues/262)) ([9a45817](https://github.com/reanahub/reana-workflow-engine-cwl/commit/9a45817075f98e04405845f0d49cbcd86ee95556))
* [Continuous integration] **release-please:** initial configuration ([#256](https://github.com/reanahub/reana-workflow-engine-cwl/issues/256)) ([bcd87d1](https://github.com/reanahub/reana-workflow-engine-cwl/commit/bcd87d1bbaa4c9b589e4025989ff880594af2b3d))
* [Continuous integration] **release-please:** update version in Dockerfile ([#259](https://github.com/reanahub/reana-workflow-engine-cwl/issues/259)) ([0961257](https://github.com/reanahub/reana-workflow-engine-cwl/commit/096125709172e6bea1510a9fd2fdcb90299fac8b))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#262](https://github.com/reanahub/reana-workflow-engine-cwl/issues/262)) ([6568b9b](https://github.com/reanahub/reana-workflow-engine-cwl/commit/6568b9b229141dd8dd2a261a833057358143590f))
* [Documentation] **authors:** complete list of contributors ([#266](https://github.com/reanahub/reana-workflow-engine-cwl/issues/266)) ([2960cd9](https://github.com/reanahub/reana-workflow-engine-cwl/commit/2960cd9c06a8e12283822ec9fbf87aba7b9b9fb5))
* [Documentation] **conformance-tests:** update CWL conformance test badges ([#264](https://github.com/reanahub/reana-workflow-engine-cwl/issues/264)) ([45afa2e](https://github.com/reanahub/reana-workflow-engine-cwl/commit/45afa2efd984fd84bbae48fde6ca663f70dd86dc))

#### reana-workflow-engine-serial [0.9.3](https://github.com/reanahub/reana-workflow-engine-serial/compare/0.9.2...0.9.3) (2024-03-04)

* [Build] **docker:** install correct extras of reana-commons submodule ([#196](https://github.com/reanahub/reana-workflow-engine-serial/issues/196)) ([b23f4df](https://github.com/reanahub/reana-workflow-engine-serial/commit/b23f4df602d80d62626e8e907181a8c710eb662f))
* [Build] **docker:** non-editable submodules in "latest" mode ([#190](https://github.com/reanahub/reana-workflow-engine-serial/issues/190)) ([03a15cf](https://github.com/reanahub/reana-workflow-engine-serial/commit/03a15cfa7973152f9923ecade412d8eab3ea80e3))
* [Build] **python:** bump all required packages as of 2024-03-04 ([#200](https://github.com/reanahub/reana-workflow-engine-serial/issues/200)) ([ffc8aec](https://github.com/reanahub/reana-workflow-engine-serial/commit/ffc8aec739e2284f301586d47618ff6c4142643a))
* [Build] **python:** bump shared REANA packages as of 2024-03-04 ([#200](https://github.com/reanahub/reana-workflow-engine-serial/issues/200)) ([47c26cc](https://github.com/reanahub/reana-workflow-engine-serial/commit/47c26ccfbfdfc7419c4a6fab1d7abf95a667e4e2))
* [Bug fixes] **progress:** handle stopped jobs ([#195](https://github.com/reanahub/reana-workflow-engine-serial/issues/195)) ([a232a76](https://github.com/reanahub/reana-workflow-engine-serial/commit/a232a76627e09bfb401de4f547540c6012357986))
* [Code refactoring] **docs:** move from reST to Markdown ([#198](https://github.com/reanahub/reana-workflow-engine-serial/issues/198)) ([7507d12](https://github.com/reanahub/reana-workflow-engine-serial/commit/7507d1243af43f4621e117f4f92569f4dd7271f6))
* [Continuous integration] **commitlint:** addition of commit message linter ([#191](https://github.com/reanahub/reana-workflow-engine-serial/issues/191)) ([b7a6ef1](https://github.com/reanahub/reana-workflow-engine-serial/commit/b7a6ef18dae95efae7af791094b5ff79369705b0))
* [Continuous integration] **commitlint:** allow release commit style ([#201](https://github.com/reanahub/reana-workflow-engine-serial/issues/201)) ([b50b6d0](https://github.com/reanahub/reana-workflow-engine-serial/commit/b50b6d0398fc6d6e4c4704d3698d811b7088921d))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#197](https://github.com/reanahub/reana-workflow-engine-serial/issues/197)) ([1813ac3](https://github.com/reanahub/reana-workflow-engine-serial/commit/1813ac3a88cd8e33a59040c6bd72ed048a151654))
* [Continuous integration] **release-please:** initial configuration ([#191](https://github.com/reanahub/reana-workflow-engine-serial/issues/191)) ([d40a675](https://github.com/reanahub/reana-workflow-engine-serial/commit/d40a675cab6b6e8c7631d503358016d427bdac3c))
* [Continuous integration] **release-please:** update version in Dockerfile ([#194](https://github.com/reanahub/reana-workflow-engine-serial/issues/194)) ([52c34ec](https://github.com/reanahub/reana-workflow-engine-serial/commit/52c34ec2003fd09b8a65ef3cff61b7f9a105041e))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#197](https://github.com/reanahub/reana-workflow-engine-serial/issues/197)) ([5565b29](https://github.com/reanahub/reana-workflow-engine-serial/commit/5565b29ac7b431561af2cd43e6ed882bbdf57126))
* [Documentation] **authors:** complete list of contributors ([#199](https://github.com/reanahub/reana-workflow-engine-serial/issues/199)) ([e9b25b6](https://github.com/reanahub/reana-workflow-engine-serial/commit/e9b25b6ab37421971d02c52422ed19fce249b4ea))

#### reana-workflow-engine-snakemake [0.9.3](https://github.com/reanahub/reana-workflow-engine-snakemake/compare/0.9.2...0.9.3) (2024-03-04)

* [Build] **docker:** install correct extras of reana-commons submodule ([#79](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/79)) ([fd9b88a](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/fd9b88a857ba016343d956e42a49b6fbc906f068))
* [Build] **docker:** non-editable submodules in "latest" mode ([#73](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/73)) ([c3595c2](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/c3595c297e90f74a9215fd76c6d6b5f69d640440))
* [Build] **python:** bump all required packages as of 2024-03-04 ([#85](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/85)) ([66e81e2](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/66e81e2148ad4ba72099a90dbb556454df3cfc99))
* [Build] **python:** bump shared REANA packages as of 2024-03-04 ([#85](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/85)) ([d07f91f](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/d07f91f6f725050c681c66ec920727f26db3fdbf))
* [Features] **config:** get max number of parallel jobs from env vars ([#84](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/84)) ([69cfad4](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/69cfad460b240e5dbafea42137d891d6fea607a5))
* [Features] **executor:** upgrade to Snakemake v7.32.4 ([#81](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/81)) ([4a3f359](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/4a3f3592c8dd3f323e81850f5bdfae45ea893825))
* [Bug fixes] **progress:** handle stopped jobs ([#78](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/78)) ([4829d80](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/4829d80a5e03ab5788fb6646bd792a7345abe14a))
* [Code refactoring] **docs:** move from reST to Markdown ([#82](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/82)) ([31de94f](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/31de94f79b1955328961d506ce9d8d4efbe7227f))
* [Continuous integration] **commitlint:** addition of commit message linter ([#74](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/74)) ([145b7e7](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/145b7e716a784c340e2ecdca5619b3ed97325b1b))
* [Continuous integration] **commitlint:** allow release commit style ([#86](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/86)) ([fd032db](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/fd032db1605ac1a295a0eac5c32799707d78cd6b))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#80](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/80)) ([b677913](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/b677913aef2df090103d461bc71dc2cde42b4212))
* [Continuous integration] **release-please:** initial configuration ([#74](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/74)) ([9b16bd0](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/9b16bd052903be4a8c567b2e71f7b56a601982b4))
* [Continuous integration] **release-please:** update version in Dockerfile ([#77](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/77)) ([3c35a67](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/3c35a67db7c181e23f28fda6152f40c8251f9b74))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#80](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/80)) ([ad15c0d](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/ad15c0d0e2020fd874a9eed5c4b36e320129b9eb))
* [Documentation] **authors:** complete list of contributors ([#83](https://github.com/reanahub/reana-workflow-engine-snakemake/issues/83)) ([4782678](https://github.com/reanahub/reana-workflow-engine-snakemake/commit/478267864a20da6ab4d7f99be5592fcf19a20ca1))

#### reana-workflow-engine-yadage [0.9.4](https://github.com/reanahub/reana-workflow-engine-yadage/compare/0.9.3...0.9.4) (2024-03-04)

* [Build] **docker:** install correct extras of reana-commons submodule ([#256](https://github.com/reanahub/reana-workflow-engine-yadage/issues/256)) ([8b4caf0](https://github.com/reanahub/reana-workflow-engine-yadage/commit/8b4caf033a765d2db77942a94a58807ac2230ca7))
* [Build] **docker:** non-editable submodules in "latest" mode ([#249](https://github.com/reanahub/reana-workflow-engine-yadage/issues/249)) ([a57716a](https://github.com/reanahub/reana-workflow-engine-yadage/commit/a57716a5d7ca6c453f3ed6b977226e47139a9ead))
* [Build] **python:** bump all required packages as of 2024-03-04 ([#261](https://github.com/reanahub/reana-workflow-engine-yadage/issues/261)) ([2a02e19](https://github.com/reanahub/reana-workflow-engine-yadage/commit/2a02e19bbf1a3c8b29f8185e4946d382aa8f27e5))
* [Build] **python:** bump shared REANA packages as of 2024-03-04 ([#261](https://github.com/reanahub/reana-workflow-engine-yadage/issues/261)) ([493aee1](https://github.com/reanahub/reana-workflow-engine-yadage/commit/493aee14c1224d5d961c792cc12d21bff314b007))
* [Bug fixes] **progress:** correctly handle running and stopped jobs ([#258](https://github.com/reanahub/reana-workflow-engine-yadage/issues/258)) ([56ef6a4](https://github.com/reanahub/reana-workflow-engine-yadage/commit/56ef6a4e434d82d8cfb9916bcfa84a0219bc2e03))
* [Code refactoring] **docs:** move from reST to Markdown ([#259](https://github.com/reanahub/reana-workflow-engine-yadage/issues/259)) ([37f05e6](https://github.com/reanahub/reana-workflow-engine-yadage/commit/37f05e6f864c33b721f7926f60d6f68f9d2f841a))
* [Continuous integration] **commitlint:** addition of commit message linter ([#251](https://github.com/reanahub/reana-workflow-engine-yadage/issues/251)) ([f180e21](https://github.com/reanahub/reana-workflow-engine-yadage/commit/f180e211438df74e23b5f538710d08afb92ae6b2))
* [Continuous integration] **commitlint:** allow release commit style ([#262](https://github.com/reanahub/reana-workflow-engine-yadage/issues/262)) ([1b8b6b8](https://github.com/reanahub/reana-workflow-engine-yadage/commit/1b8b6b87782c4ea006d6bd5ca5b3f2e1bb721287))
* [Continuous integration] **commitlint:** check for the presence of concrete PR number ([#257](https://github.com/reanahub/reana-workflow-engine-yadage/issues/257)) ([9ddb488](https://github.com/reanahub/reana-workflow-engine-yadage/commit/9ddb4885fbc008c25394adde08dd94411217f5fe))
* [Continuous integration] **release-please:** initial configuration ([#251](https://github.com/reanahub/reana-workflow-engine-yadage/issues/251)) ([dc4fa7a](https://github.com/reanahub/reana-workflow-engine-yadage/commit/dc4fa7a741af36b1fc1968eba18a98597ace26c9))
* [Continuous integration] **release-please:** update version in Dockerfile ([#254](https://github.com/reanahub/reana-workflow-engine-yadage/issues/254)) ([8f18751](https://github.com/reanahub/reana-workflow-engine-yadage/commit/8f18751696f0ebbf5c0d08b08d9c3e58ee3e3897))
* [Continuous integration] **shellcheck:** fix exit code propagation ([#257](https://github.com/reanahub/reana-workflow-engine-yadage/issues/257)) ([8831d9e](https://github.com/reanahub/reana-workflow-engine-yadage/commit/8831d9e319545889b6e4ce1a589e140bb2fa2275))
* [Documentation] **authors:** complete list of contributors ([#260](https://github.com/reanahub/reana-workflow-engine-yadage/issues/260)) ([68f97a0](https://github.com/reanahub/reana-workflow-engine-yadage/commit/68f97a0aff07b16e2707423185925c8d6d22c33b))

## 0.9.2 (2023-12-19)

* Users:

  * Adds web interface form allowing to generate launcher URL for any user-provided public analysis, as well as the Markdown snippet for the corresponding Launch-on-REANA badge.
  * Adds web interface option to delete all the runs of a workflow.
  * Changes the Launch-on-REANA web interface page to improve how workflow parameters are shown by displaying them inside a table.
  * Changes CVMFS support to allow users to automatically mount any available repository.
  * Changes the REANA specification schema to use the `draft-07` version of the JSON Schema specification.
  * Changes `reana-client validate` command to show detailed errors when the specification file is not a valid YAML file.
  * Changes validation of REANA specification to make the `environment` property mandatory for the steps of serial workflows.
  * Changes validation of REANA specification to raise a warning for unexpected properties for the steps of serial workflows.
  * Changes validation of REANA specification to report improved validation warnings which also indicate where unexpected properties are located in the file.
  * Changes workflow restarts to allow for more than nine restarts of the same workflows.
  * Changes workflow scheduler logging behaviour to also report the main reason behind scheduling errors to the users.
  * Fixes `reana-client list` command to accept case-insensitive column names when sorting the returned workflow runs via the `--sort` option.
  * Fixes `reana-client run` wrapper command for workflows that do not contain `inputs` clause in their specification.
  * Fixes `reana-client`'s `create_workflow_from_json` API function to always load and send the workflow specification to the server.
  * Fixes creation of image thumbnails for output files in Snakemake HTML execution reports.

* Administrators:

  * Changes several database index definitions in order to improve performance of most common database queries.
  * Changes the names of database table, column, index and key constraints in order to follow the SQLAlchemy upstream naming conventions everywhere.
  * Changes the `Workflow` table to replace the `run_number` column with two new columns `run_number_major` and `run_number_minor` in order to allow for more than nine restarts of user workflows.
  * Changes CVMFS support to allow users to automatically mount any available repository, thanks to CVMFS CSI v2.
  * Fixes the mounting of CVMFS volumes for the REANA deployments that use non-default Kubernetes namespace.
  * Fixes container image building of cluster components for the arm64 architecture.
  * Fixes job monitoring in cases when job creation fails, for example when it is not possible to successfully mount volumes.
  * Fixes job status consumer exception while attempting to fetch workflow engine logs for workflows that could not have been successfully scheduled.
  * Fixes the creation of Kubernetes jobs by retrying in case of error and by correctly handling the error after reaching the retry limit.

* Developers:

  * Adds automated multi-platform container image building of cluster components for amd64 and arm64 architectures.
  * Adds new `--image-name` option to the `reana-dev docker-push` command to customise the name of the docker image to publish.
  * Adds new `--platform` option to the `reana-dev docker-build` and `reana-dev release-docker` commands to build and publish multi-platform images.
  * Adds new `--registry` option to the `reana-dev docker-push` and `reana-dev release-docker` commands to specify the registry where the built docker images should be pushed to.
  * Adds new `--tags-only` option to the `reana-dev release-docker` command to only print the final docker image names, without pushing the images to the registry.
  * Adds new `reana-dev git-create-release-branch` command to create a new Git branch for a new release.
  * Adds new `reana-dev git-upgrade-requirements` command to upgrade the `requirements.txt` file before a new release.
  * Changes `reana-dev git-fork` and `reana-dev git-create-pr` to use the `gh` CLI client instead of `hub`.
  * Changes `reana-dev python-run-tests` command to allow excluding certain Python components.
  * Changes `reana-dev python-run-tests` command to allow execution of selected pytests only by passing over `PYTEST_ADDOPTS` environment variable.
  * Changes validation of REANA specification to expose functions for loading workflow input parameters and workflow specifications.
  * Changes version of `reana-ui` Node.js Docker image from 16 to 18.
  * Changes the workflow deletion endpoint to return a different and more appropriate message when deleting all the runs of a workflow.
  * Changes the workflow list endpoint on how pagination is performed in order to avoid counting twice the total number of records.
  * Fixes `reana-dev python-run-tests` command to create Python-3.8 based virtual environments to use the same version as container images.

## 0.9.1 (2023-09-27)

* Users:

  * Adds support for Python 3.12.
  * Adds support for previewing PDF files present in a workflow's workspace.
  * Adds support for previewing ROOT files present in a workflow's workspace.
  * Adds support for signing-in with a custom third-party Keycloak instance.
  * Adds a new menu item to the workflow actions popup to allow stopping running workflows.
  * Adds `prune` command to delete all intermediate files of a given workflow. Use with care.
  * Changes the deletion of a workflow to automatically delete an open interactive session attached to its workspace.
  * Changes the workflow deletion message to clarify that attached interactive sessions are also closed when a workflow is deleted.
  * Changes the workflow progress bar to always display it as completed for finished workflows.
  * Changes the interactive session notification to also report that the session will be closed after a specified number of days of inactivity.
  * Changes the workflow-details page to make it possible to scroll through the list of workflow steps in the job logs section.
  * Changes the workflow-details page to not automatically refresh the selected job when viewing the related logs, but keeping the user-selected one active.
  * Changes the page titles to conform to the same sentence case style.
  * Changes the launcher page to show warnings when validating the REANA specification file of the workflow to be launched.
  * Changes `open` command to inform user about the auto-closure of interactive sessions after a certain inactivity timeout.
  * Changes `validate` command to display non-critical validation warnings when checking the REANA specification file.
  * Changes Rucio authentication helper to allow users to override the Rucio server and authentication hosts independently of VO name.
  * Fixes job status inconsistency when stopping a workflow by setting the job statuses to `stopped` for any running jobs.
  * Fixes calculation of workflow runtime durations for stopped workflows.
  * Fixes `list` command to correctly list workflows when sorting them by their run number or by the size of their workspace.
  * Fixes `du` command help message typo.
  * Fixes `validation --environments` command to correctly handle fully-qualified image names.
  * Fixes deletion of failed jobs not being performed when Kerberos is enabled.
  * Fixes job monitoring to consider OOM-killed jobs as failed.
  * Fixes detection of default Rucio server and authentication host for ATLAS VO.
  * Fixes the reported total number of jobs for restarted workflows by excluding cached jobs that were simply reused from previous runs in the workspace and not really executed by Snakemake.
  * Fixes an issue where Snakemake workflows could get stuck waiting for already-finished jobs.

* Administrators:

  * Adds support for Kubernetes clusters 1.26, 1.27, 1.28.
  * Adds new configuration option `components.reana_ui.launcher_examples` to customise the demo examples that are shown in the launch page in the REANA UI.
  * Adds new configuration option `interactive_sessions.maximum_inactivity_period` to set a limit in days for the maximum inactivity period of interactive sessions after which they will be closed.
  * Adds new configuration option `interactive_sessions.cronjob_schedule` to set how often interactive session cleanup should be performed.
  * Adds new configuration option `ingress.extra` to define extra Ingress resources, in order to support redirecting HTTP requests to HTTPS with traefik v2 version.
  * Adds new configuration option `ingress.tls.hosts` to define hosts that are present in the TLS certificate, in order to support cert-manager's automatic creation of certificates.
  * Adds new configuration option `notifications.email_config.smtp_ssl` to use SSL when connecting to the SMTP email server.
  * Adds new configuration option `notifications.email_config.smtp_starttls` to use the STARTTLS command to enable encryption after connecting to the SMTP email server.
  * Adds new configuration option `components.reana_ui.file_preview_size_limit` to set the maximum file size that can be previewed in the web interface.
  * Adds new configuration options `login` and `secrets.login` for configuring Keycloak SSO login with third-party authentication services.
  * Adds new `interactive-session-cleanup` command that can be used by REANA administrators to close interactive sessions that are inactive for more than the specified number of days.
  * Adds progress meter to the logs of the periodic quota updater.
  * Adds the content of the `secrets.gitlab.REANA_GITLAB_HOST` configuration option to the list of GitLab instances from which it is possible to launch a workflow.
  * Changes uWSGI configuration to increase buffer size, add vacuum option, etc.
  * Changes CPU and disk quota calculations to improve the performance of periodic quota updater.
  * Changes the system status report to simplify and clarify the disk usage summary.
  * Changes `check-workflows` command to also check the presence of workspaces on the shared volume.
  * Changes `check-workflows` command to not show in-sync runs by default. If needed, they can be shown using the new `--show-all` option.
  * Changes `reana-admin` command options to require the passing of `--admin-access-token` argument more globally.
  * Changes the k8s specification for interactive session pods to include labels for improved subset selection of objects.
  * Changes the k8s specification for interactive session ingress resource to include annotations.
  * Changes nginx configuration to save bandwidth by serving gzip-compressed static files.
  * Changes HTCondor to version 9.0.17 (LTS).
  * Fixes uWSGI memory consumption on systems with very high allowed number of open files.
  * Fixes cronjob failures due to database connection issues when REANA is deployed with non-default namespace or prefix.
  * Fixes `ingress.enabled` option to correctly enable or disable the creation of Ingresses.
  * Fixes graceful shutdown for reana-server and reana-workflow-controller.
  * Fixes the workflow priority calculation to avoid workflows stuck in the `queued` status when the number of allowed concurrent workflow is set to zero.
  * Fixes GitLab integration to automatically redirect the user to the correct URL when the access request is accepted.
  * Fixes authentication flow to correctly deny access to past revoked tokens in case the same user has also other new active tokens.
  * Fixes email templates to show the correct `kubectl` commands when REANA is deployed inside a non-default namespace or with a custom component name prefix.
  * Fixes email sender for system emails to `notifications.email_config.sender` Helm value.
  * Fixes email receiver for token request emails to use `notifications.email_config.receiver` Helm value.
  * Fixes `quota-set-default-limits` command to propagate default quota limits to all users without custom quota limit values.
  * Fixes job status consumer to correctly rollback the database transaction when an error occurs.
  * Fixes intermittent Slurm connection issues by DNS-resolving the Slurm head node IPv4 address before establishing connections.
  * Fixes Slurm command generation issues when using fully-qualified image names.
  * Fixes high memory usage of RabbitMQ by limiting the maximum number of open file descriptors.
  * Removes support for Kubernetes version prior to 1.21.

* Developers:

  * Adds new `prune_workspace` endpoint to allow users to delete all the files of a workflow, specifying whether to also delete the inputs and/or the outputs.
  * Adds the timestamp of when the workflow was stopped (`run_stopped_at`) to the workflow list and the workflow status endpoints.
  * Adds unique error messages to Kubernetes job monitor to more easily identify source of problems.
  * Adds new `--parallel` option to `docker-build`, `cluster-build` and `run-ci` to build multiple docker images in parallel.
  * Changes `launch` endpoint to also include the warnings of the validation of the workflow specification.
  * Changes OpenAPI specification of the `info` endpoint to return the maximum inactivity time before automatic closure of interactive sessions.
  * Changes `apispec` dependency version in order to be compatible with `PyYAML` v6.
  * Changes Paramiko to version 3.0.0.
  * Changes remote storage file support for Snakemake workflows to use XRootD 5.6.0.
  * Fixes `cluster-deploy`, `cluster-undeploy` and `client-setup-environment` commands when using custom instance name or kubernetes namespace.
  * Fixes the `git-tag` command to display the component name.
  * Fixes container image names to be Podman-compatible.
  * Fixes location of HTCondor build dependencies.

## 0.9.0 (2023-01-26)

* Users:

  * Adds support for Rucio authentication for workflow jobs.
  * Adds support for Kerberos authentication for workflow orchestration.
  * Adds support for specifying `slurm_partition` and `slurm_time` for Slurm compute backend jobs.
  * Adds support for XRootD remote file locations in Snakemake workflow specification definitions.
  * Adds support for Python 3.11.
  * Adds Launch on REANA page allowing the submission of workflows via badge-clicking.
  * Adds notifications to inform users when critical levels of quota usage is reached.
  * Adds 404 Not Found error page.
  * Adds tab titles to all the pages.
  * Adds the `REANA_WORKSPACE` environment variable to jupyter notebooks and terminals.
  * Adds option to sort workflows by most disk and cpu quota usage to the workflow list endpoint.
  * Adds support for specifying and listing workspace file retention rules.
  * Adds support for `.gitignore` and `.reanaignore` to specify files that should not be uploaded to REANA.
  * Adds `retention-rules-list` command to list the retention rules of a workflow.
  * Changes REANA specification to allow specifying `retention_days` for the workflow.
  * Changes default Slurm partition to `inf-short`.
  * Changes GitLab integration to also retrieve user's projects that are in groups and subgroups.
  * Changes the workflow-details page to show the logs of the workflow engine.
  * Changes the workflow-details page to show file sizes in a human-readable format.
  * Changes the workflow-details page to show the workspace's retention rules.
  * Changes the workflow-details page to show the duration of the workflow's jobs.
  * Changes the workflow-details page to display a label of the workflow launcher URL remote origin.
  * Changes the workflow-details page to periodically refresh the content of the page.
  * Changes the workflow-details page to refresh after the deletion of a workflow.
  * Changes the workflow-list page to add a way to hide deleted workflows.
  * Changes the workflow-list page to add new workflows sorting options by most used disk and cpu quota.
  * Changes the deletion of a workflow to always clean up the workspace and to update the user disk quota usage.
  * Changes the CWD of jupyter's terminals to the directory of the workflow's workspace.
  * Changes percentage ranges used to calculate the health status of user resource quota usage.
  * Changes `create` and `restart` commands to always upload the REANA specification file.
  * Changes `delete` command to always delete the workflow's workspace.
  * Changes `delete_workflow` Python API function to always delete the workflow's workspace.
  * Changes `download` command to add the possibility to write files to the standard output via `-o -` option.
  * Changes `list` command to hide deleted workflows by default.
  * Changes `list` command to allow displaying deleted workflows via `--all` and `--show-deleted-runs` options.
  * Changes `list` and `status` commands to allow displaying the duration of workflows with the `--include-duration` option.
  * Changes `mv` command to allow moving files while a workflow is running.
  * Changes `upload` command to prevent uploading symlinks.
  * Changes `validation --environment` command to use Docker registry v2 APIs to check that a Docker image exists in DockerHub.
  * Fixes `list` command to highlight the workflow specified in `REANA_WORKON` correctly.
  * Fixes `secrets-delete` command error message when deleting non existing secrets.
  * Fixes `start` command to report failed workflows as errors.
  * Fixes `start` and `run` commands to correctly follow the execution of the workflow until termination.
  * Fixes `status` command to respect output format provided by the `--format` option.
  * Fixes `upload` command to report when input directories are listed under the `files` section in the REANA specification file and vice versa.
  * Fixes `validate --environment` command to detect illegal whitespace characters in Docker image names.
  * Fixes Kerberos authentication for long-running workflows by renewing the Kerberos ticket periodically.
  * Fixes status reporting for failed CWL and Snakemake jobs that were incorrectly considered successful.
  * Fixes redirection chain for non-signed-in CERN SSO users to access the desired target page after sign-in.
  * Fixes the ordering by size of the files showed in the `Workspace` tab of the workflow-details page.
  * Fixes CERN OIDC authentication to possibly allow eduGAIN and social login users.
  * Fixes wrong numbering of restarted workflows by limiting the number of times a workflow can be restarted to nine.

* Administrators:

  * Adds new configuration environment variable `reana_server.environment.REANA_SCHEDULER_REQUEUE_COUNT` to set workflow requeue count in case of scheduling errors or busy cluster situations.
  * Adds "infinity" option to `REANA_SCHEDULER_REQUEUE_COUNT` to disable requeue count.
  * Adds support for Kubernetes clusters 1.22, 1.23, 1.24, 1.25.
  * Adds new configuration option `workspaces.retention_rules.maximum_period` to set a default period for workspace retention rules.
  * Adds new configuration option `workspaces.retention_rules.cronjob_schedule` to set how often pending retention rules should be applied.
  * Adds configuration environment variable `reana_server.environment.REANA_RATELIMIT_SLOW` to limit API requests to some protected endpoints e.g launch workflow.
  * Adds configuration environment variable `reana_server.environment.REANA_WORKFLOW_SCHEDULING_READINESS_CHECK_LEVEL` to define checks that are performed to assess whether the cluster is ready to start new workflows.
  * Adds new configuration option `ingress.tls.self_signed_cert` to enable the generation of a self-signed TLS certificate.
  * Adds new configuration option `ingress.tls.secret_name` to specify the name of the Kubernetes secret containing the TLS certificate to be used.
  * Adds support for configuring an additional volume to be used by the database and the message broker.
  * Adds new configuration option `maintenance.enabled` to scale down the cluster for maintenance.
  * Adds support for Unicode characters inside email body.
  * Adds `queue-consume` command that can be used by REANA administrators to remove specific messages from the queue.
  * Adds `retention-rules-apply` command that can be used by REANA administrators to apply pending retention rules.
  * Adds `retention-rules-extend` command that can be used by REANA administrators to extend the duration of active retentions rules.
  * Adds `check-workflows` command that can be used by REANA administrators to check for out-of-sync workflows and interactive sessions.
  * Changes configuration option `quota.workflow_termination_update_policy` to deactivate workflow termination accounting by default.
  * Changes Helm template to use PostgreSQL 12.13 version.
  * Changes the base image for most of the components to Ubuntu 20.04 LTS and reduces final Docker image size by removing build-time dependencies.
  * Changes `reana-auth-vomsproxy` sidecar to the latest stable version to support client-side proxy file generation technique and ESCAPE VOMS.
  * Changes OAuth configuration to enable the new CERN SSO.
  * Changes job status consumer to improve logging for not-alive workflows.
  * Changes the deployment of interactive sessions to improve security by not automounting the Kubernetes service account token.
  * Changes the deployment of job-controller to avoid unnecessarily mounting the database's directory.
  * Changes the announcements to support limited HTML markup.
  * Changes REANA specification loading functionality to allow specifying different working directories.
  * Changes global setting of maximum number of parallel jobs to 300 for Snakemake workflow engine.
  * Fixes job status consumer by discarding invalid job IDs.
  * Fixes GitLab integration error reporting in case user exceeds CPU or Disk quota usage limits.
  * Fixes issue when irregular number formats are passed to `REANA_SCHEDULER_REQUEUE_COUNT` configuration environment variable.
  * Fixes quota updater to reduce memory usage.
  * Fixes conversion of possibly-negative resource usage values to human-readable formats.
  * Fixes disk quota updater to prevent setting negative disk quota usage values.
  * Removes support for Kubernetes version prior to 1.19.

* Developers:

  * Adds OpenAPI specification support for `launch` endpoint that allows running workflows from remote sources.
  * Adds OpenAPI specification support for `get_workflow_retention_rules` endpoint that allows to retrieve the workspace file retention rules of a workflow.
  * Adds the remote origin of workflows submitted via Launch-on-REANA (`launcher_url`) to the workflow list endpoint.
  * Adds common utility functions for managing workspace files to `reana-commons`.
  * Changes default consumer prefetch count to handle 10 messages instead of 200 in order to reduce the probability of 406 PRECONDITION errors on message acknowledgement.
  * Changes `git-upgrade-shared-modules` to generate the correct upper-bound in `setup.py`.
  * Changes REANA specification loading and validation functionalities by porting some of the logic to `reana-commons`.
  * Changes OpenAPI specification to include missing response schema elements.
  * Changes the Kubernetes Python client to use the `networking/v1` API.
  * Changes the deployment of interactive sessions to use `networking/v1` Kubernetes API.
  * Changes to Flask v2.
  * Changes `/api/info` endpoint to also include the kubernetes maximum memory limit, the kubernetes default memory limit and the maximum workspace retention period.
  * Changes `start_workflow` endpoint to validate the REANA specification of the workflow.
  * Changes `create_workflow` endpoint to populate workspace retention rules for the workflow.
  * Changes `start_workflow` endpoint to disallow restarting a workflow when retention rules are pending.
  * Changes API rate limiter error messages to be more verbose.
  * Changes workflow scheduler to allow defining the checks needed to assess whether the cluster can start new workflows.
  * Changes workflow list endpoint to add the possibility to filter by workflow ID.
  * Changes the `move_files` endpoint to allow moving files while a workflow is running.
  * Changes the k8s specification of interactive sessions' pods to remove the environment variables used for service discovery.
  * Changes GitLab integration to use `reana` as pipeline name instead of `default` when setting status of a commit.
  * Changes the loading of Snakemake specifications to preserve the current working directory.
  * Changes the Invenio dependencies to the latest versions.
  * Fixes the submission of jobs by stripping potential leading and trailing whitespaces in Docker image names.
  * Fixes `fetchWorkflow` action to fetch a specific workflow instead of the entire user workflow list. (reana-ui)
  * Fixes the download of files by changing the default MIME type to `application/octet-stream`.
  * Fixes the workflow list endpoint to correctly parse the boolean parameters `include_progress`, `include_workspace_size` and `include_retention_rules`.

## 0.8.1 (2022-02-15)

* Users:

  * Adds support for specifying `kubernetes_job_timeout` for Kubernetes compute backend jobs.
  * Adds Kubernetes job memory limits validation before accepting workflows for execution.
  * Adds support for HTML preview of workspace files in the web user interface.
  * Adds an option to search for concrete file names in the workflow's workspace web user interface page.
  * Changes the Cluster Health web interface page to display the cluster status information based on resource availability rather than only usage.
  * Changes `info` command to include the list of supported compute backends.
  * Fixes workflow stuck in pending status due to early Yadage failures.
  * Fixes formatting of error messages and sets appropriate exit status codes.

* Administrators:

  * Adds new configuration option to set default job timeout value for the Kubernetes compute backend jobs (`kubernetes_jobs_timeout_limit`).
  * Adds new configuration option to set maximum job timeout that users can assign to their jobs for the Kubernetes compute backend (`kubernetes_jobs_max_user_timeout_limit`).
  * Adds new configuration option `compute_backends` to specify the supported list of compute backends for validation purposes.
  * Adds new configuration option `reana_server.uwsgi.log_all` to toggle the logging of all the HTTP requests.
  * Adds new configuration options `reana_server.uwsgi.log_4xx` and `reana_server.uwsgi.log_5xx` to only log HTTP error requests, i.e. HTTP requests with status code 4XX and 5XX. To make this configuration effective `reana_server.uwsgi.log_all` must be `false`.
  * Adds new configuration options `node_label_infrastructuremq` and `node_label_infrastructuredb` to have the possibility to run the Message Broker and the Database pods in specific nodes.
  * Changes uWSGI configuration to log all HTTP requests in REANA-Server by default.
  * Changes `quota.disk_update` to `quota.periodic_update_policy` to also update the CPU quota. Keeps `quota.disk_update` for backward compatibility.
  * Changes the name of configuration option `quota.termination_update_policy` to `quota.workflow_termination_update_policy`. Keeps `quota.termination_update_policy` for backward compatibility.

* Developers:

  * Adds workflow name validation to the `create_workflow` endpoint, restricting special characters like dots.
  * Changes `/api/info` endpoint to return a list of supported compute backends.
  * Changes `/api/status` endpoint to calculate the cluster health status based on the availability instead of the usage.
  * Changes the way of determining Snakemake job statuses, polling the Job Controller API instead of checking local files.

## 0.8.0 (2021-11-30)

* Users:

  * Adds support for running and validating Snakemake workflows.
  * Adds support for `outputs.directories` in `reana.yaml` allowing to easily download output directories.
  * Adds new command `quota-show` to retrieve information about total CPU and Disk usage and quota limits.
  * Adds new command `info` that retrieves general information about the cluster, such as available workspace path settings.
  * Changes `validate` command to add the possibility to check the workflow against server capabilities such as desired workspace path via `--server-capabilities` option.
  * Changes `list` command to add the possibility to filter by workflow status and search by workflow name via `--filter` option.
  * Changes `list` command to add the possibility to filter and display all the runs of a given workflow via `-w` option.
  * Changes `list` command to stop including workflow progress and workspace size by default. Please use new options `--include-progress` and `--include-workspace-size` to show this information.
  * Changes `list --sessions` command to display the status of interactive sessions.
  * Changes `logs` command to display also the start and finish times of individual jobs.
  * Changes `ls` command to add the possibility to filter by file name, size and last-modified values via `--filter` option.
  * Changes `du` command to add the possibility filter by file name and size via `--filter` option.
  * Changes `delete` command to prevent hard-deletion of workflows.
  * Changes Yadage workflow specification loading to be done in `reana-commons`.
  * Changes CWL workflow engine to `cwltool` version `3.1.20210628163208`.
  * Removes support for Python 2.7. Please use Python 3.6 or higher from now on.

* Administrators:

  * Adds new configuration options `node_label_runtimebatch`, `node_label_runtimejobs`, `node_label_runtimesessions` allowing to set cluster node labels for splitting runtime workload into dedicated workflow batch nodes, workflow job nodes and interactive session nodes.
  * Adds new configuration option `workspaces.paths` allowing to set a dictionary of available workspace paths to pairs of `cluster_node_path:cluster_pod_mountpath` for mounting directories from cluster nodes.
  * Adds new configuration option `quota.enabled` to enable or disable CPU and Disk quota accounting for users.
  * Adds new configuration option `quota.termination_update_policy` to select the quota resources such as CPU and Disk for which the quota usage will be calculated immediately at the workflow termination time.
  * Adds new periodic cron job to update Disk quotas nightly. Useful if the `quota.termination_update_policy` does not include Disk quota resource.
  * Adds configuration environment variable `reana_server.environment.REANA_WORKFLOW_SCHEDULING_POLICY` allowing to set workflow scheduling policy (first-in first-out, user-balanced and workflow-complexity balanced).
  * Adds configuration environment variables `reana_server.environment.REANA_RATELIMIT_GUEST_USER`, `reana_server.environment.REANA_RATELIMIT_AUTHENTICATED_USER` allowing to set REST API rate limit values.
  * Adds configuration environment variable `reana_server.environment.REANA_SCHEDULER_REQUEUE_SLEEP` to set a time to wait between processing queued workflows.
  * Adds configuration environment variable `reana_workflow_controller.environment.REANA_JOB_STATUS_CONSUMER_PREFETCH_COUNT` allowing to set a prefetch count for the job status consumer.
  * Adds support for Kubernetes 1.21 version clusters.
  * Adds default `kubernetes_memory_limit` value (4 GiB) that will be used for all user jobs unless they specify otherwise.
  * Changes Helm template to use PostgreSQL 12.8 version.
  * Changes Helm template for `reana-db` component to allow 300 maximum number of database connections by default.
  * Fixes email validation procedure during `create-admin-user` command to recognize more permissive email address formats.

* Developers:

  * Changes `git-*` commands to add the possibility of excluding certain components via the `--exclude-components` option.
  * Changes `git-create-release-commit` command to bump all version files in a component.
  * Changes `git-log` command to show diff patch or to pass any wanted argument.
  * Changes `helm-upgrade-components` command to also upgrade the image tags in `prefetch-images.sh` script.

## 0.7.4 (2021-07-07)

* Users:

  * Adds support for file listing wildcard matching patterns to `ls` command.
  * Adds support for directory download and wildcard matching patterns to `download` command.
  * Adds support for specifying `kubernetes_memory_limit` for Kubernetes compute backend jobs for CWL, Serial and Yadage workflows.
  * Changes `list` command to include deleted workflows by default.
  * Changes `validate` command to warn about incorrectly used workflow parameters for each step.
  * Changes `validate` command to display more granular workflow validation output.
  * Fixes workflow step job command formatting bug for CWL workflows on HTCondor compute backend.
  * Fixes `validate` command output for verifying environment image UID values.
  * Fixes `upload_to_server()` Python API function to silently skip uploading in case of none-like inputs.
  * Fixes `validate` command for environment image validation to not test repetitively the same image found in different steps.

* Administrators:

  * Adds support for Kubernetes 1.21.
  * Adds configuration environment variable to set default job memory limits for the Kubernetes compute backend (`REANA_KUBERNETES_JOBS_MEMORY_LIMIT`).
  * Adds configuration environment variable to set maximum custom memory limits that users can assign to their jobs for the Kubernetes compute backend (`REANA_KUBERNETES_JOBS_MAX_USER_MEMORY_LIMIT`).
  * Changes HTCondor compute backend to 8.9.11 and `myschedd` package and configuration to latest versions.
  * Fixes Kubernetes job log capture to include information about failures caused by external factors such as out-of-memory situations (`OOMKilled`).

* Developers:

  * Adds new functions to serialise/deserialise job commands between REANA components.
  * Changes client dependencies to unpin six so that client may be installed in more contexts.
  * Changes cluster dependencies to remove click and pins several dependencies.
  * Changes `reana_ready()` function location to REANA-Server.

## 0.7.3 (2021-03-24)

* Users:

  * Adds `reana-client validate` options to detect possible issues with workflow input parameters and environment images.
  * Fixes problem with failed jobs being reported as still running in case of network problems.
  * Fixes job command encoding issues when dispatching jobs to HTCondor and Slurm backends.

* Administrators:

  * Adds new configuration to toggle Kubernetes user jobs clean up.
    : (`REANA_RUNTIME_KUBERNETES_KEEP_ALIVE_JOBS_WITH_STATUSES` in `components.reana_workflow_controller.environment`)
  * Improves platform resilience.

* Developers:

  * Adds new command-line options to `reana-dev run-example` command allowing full parallel asynchronous execution of demo examples.
  * Adds default configuration for developer deployment mode to keep failed workflow and job pods for easier debugging.
  * Changes job status consumer communications to improve overall platform resilience.

## 0.7.2 (2021-02-04)

* Administrators:

  * Adds support for deployments on Kubernetes 1.20 clusters.
  * Adds deployment option to disable user email confirmation step after sign-up. (`REANA_USER_EMAIL_CONFIRMATION` in `components.reana_server.environment`)
  * Adds deployment option to disable user sign-up feature completely. (`components.reana_ui.hide_signup`)
  * Adds deployment option to display CERN Privacy Notice for CERN deployments. (`components.reana_ui.cern_ropo`)

* Developers:

  * Adds support for Python 3.9.
  * Fixes minor code warnings.
  * Changes CI system to include Python flake8 and Dockerfile hadolint checkers.

## 0.7.1 (2020-11-10)

* Users:

  * Adds support for specifying `htcondor_max_runtime` and `htcondor_accounting_group` for HTCondor compute backend jobs.
  * Fixes restarting of Yadage and CWL workflows.
  * Fixes REANA \<-> GitLab synchronisation for projects having additional external webhooks.
  * Changes `ping` command output to include REANA client and server version information.

* Developers:

  * Fixes conflicting `kombu` installation requirements by requiring Celery version 4.
  * Changes `/api/you` endpoint to include REANA server version information.
  * Changes continuous integration platform from Travis CI to GitHub Actions.

## 0.7.0 (2020-10-21)

* Users:

  * Adds new `restart` command to restart previously run or failed workflows.
  * Adds option to `logs` command to filter job logs according to compute backend, docker image, job status and step name.
  * Adds option to specify operational options in the `reana.yaml` of the workflow.
  * Adds option to specify unpacked Docker images as workflow step requirement.
  * Adds option to specify Kubernetes UID for jobs.
  * Adds support for VOMS proxy as a new authentication method.
  * Adds support for pulling private Docker images.
  * Adds pagination on the workflow list and workflow detailed web interface pages.
  * Adds user profile page to the web interface.
  * Adds page refresh button to workflow detailed page.
  * Adds local user web forms for sign-in and sign-up functionalities for local deployments.
  * Fixes user experience by preventing dots as part of the workflow name to avoid confusion with restart runs.
  * Fixes workflow specification display to show runtime parameters.
  * Fixes file preview functionality experience to allow/disallow certain file formats.
  * Changes Yadage workflow engine to version 0.20.1.
  * Changes CERN HTCondor compute backend to use the new `myschedd` connection library.
  * Changes CERN Slurm compute backend to improve job status detection.
  * Changes documentation to move large parts to [docs.reana.io](http://docs.reana.io).
  * Changes `du` command output format.
  * Changes `logs` command to enhance formatting using marks and colours.
  * Changes `ping` command to perform user access token validation.
  * Changes `diff` command to improve output formatting.
  * Changes defaults to accept both `reana.yaml` and `reana.yml` filenames.
  * Changes from Bravado to requests to improve download performance.
  * Changes file loading to optimise CLI performance.

* Administrators:

  * Adds Helm chart and switches to Helm-based deployment technique instead of using now-deprecated `reana-cluster`.
  * Adds email notification service to inform administrators about system health.
  * Adds announcement configuration option to display any desired text on the web UI.
  * Adds pinning of all Python dependencies allowing to easily rebuild component images at later times.
  * Adds support for local user management and web forms for sign-in and sign-up functionalities.
  * Adds support for database upgrades using Alembic.
  * Changes installation procedures to move database initialisation and admin creation after Helm installation.
  * Changes service exposure to stop exposing unused Invenio-Accounts views.
  * Changes runtime job instantiation into the configured runtime namespace.
  * Changes CVMFS to be read-only mount.

* Developers:

  * Adds several new `reana-dev` commands to help with merging, releasing, unit testing.
  * Changes base image to use Python 3.8 for all REANA cluster components.
  * Changes pre-requisites to node version 12 and latest npm dependencies.
  * Changes back-end code formatting to respect `black` coding style.
  * Changes front-end code formatting to respect updated `prettier` version coding style.
  * Changes test strategy to start PostgreSQL DB container to run tests locally.
  * Changes auto-generated component documentation to single-page layout.

## 0.6.1 (2020-06-09)

* Administrators:

  * Fixes installation troubles for REANA 0.6.x release series by pinning several dependencies.
  * Upgrades REANA-Commons package to latest Kubernetes Python client version.
  * Amends documentation for `minikube start` to include VirtualBox hypervisor explicitly.

## 0.6.0 (2019-12-27)

* Users:

  * Adds support for HTCondor compute backend for all workflow engines (CWL, Serial, Yadage).
  * Adds support for Slurm compute backend for all workflow engines (CWL, Serial, Yadage).
  * Allows to run hybrid analysis pipelines where different parts of the workflow can run on different compute backends (HTCondor, Kubernetes, Slurm).
  * Adds support for Kerberos authentication mechanism for user workflows.
  * Introduces user secrets management commands `secrets-add`, `secrets-list` and `secrets-delete`.
  * Fixes `upload` command behaviour for uploading very large files.
  * Upgrades CWL workflow engine to 1.0.20191022103248.
  * Upgrades Yadage workflow engine to 0.20.0 with Packtivity 0.14.21.
  * Adds support for Python 3.8.
  * See additional changes in [reana-client 0.6.0 release notes](https://reana-client.readthedocs.io/en/latest/changes.html#version-0-6-0-2019-12-27).

* Administrators:

  * Upgrades to Kubernetes 1.16 and moves Traefik installation to Helm 3.0.0.
  * Creates a new Kubernetes service account for REANA with appropriate permissions.
  * Makes database connection details configurable so that REANA can connect to databases external to the cluster.
  * Autogenerates deployment secrets if not provided by administrator at cluster creation time.
  * Adds an interactive mode on cluster initialisation to allow providing deployment secrets.
  * Adds CERN specific Kerberos configuration files and CERN EOS storage support.
  * See additional changes in [reana-cluster 0.6.0 release notes](https://reana-cluster.readthedocs.io/en/latest/changes.html#version-0-6-0-2019-12-27).

* Developers:

  * Modifies the batch workflow runtime pod creation including an instance of job controller running alongside workflow engine using the sidecar pattern.
  * Adds generic job manager class and provides example classes for CERN HTCondor and CERN Slurm clusters.
  * Provides user secrets to the job container runtime tasks.
  * Adds sidecar container to the Kubernetes job pod if Kerberos authentication is required.
  * Refactors job monitoring using the singleton pattern.
  * Enriches `make` behaviour for developer-oriented installations with live code reload changes and debugging.
  * Enriches `git-status` component status reporting for developers.
  * See additional changes in [individual REANA 0.6.0 platform components](https://reana.readthedocs.io/en/latest/administratorguide.html#components).

## 0.5.0 (2019-04-24)

* Users:

  * Allows to explore workflow results by running interactive Jupyter notebook sessions on the workspace files.
  * Allows to declare computing resources needed for workflow runs, such as access to CVMFS repositories.
  * Improves `reana-client` command-line client with new options to stop workflows, diff workflows, move and remove files.
  * Upgrades CWL engine to 1.0.20181118133959.
  * See additional changes in [reana-client 0.5.0 release notes](https://reana-client.readthedocs.io/en/latest/changes.html#version-0-5-0-2019-04-24).

* Administrators:

  * Upgrades to Kubernetes 1.14, Helm 2.13 and Minikube 1.0.
  * Separates cluster infrastructure pods from runtime workflow engine pods that will be created by workflow controller.
  * Introduces configurable CVMFS and CephFS shared volume mounts.
  * Adds support for optional HTTPS protocol termination.
  * Introduces incoming workflow queue for additional safety in case of user storms.
  * Makes infrastructure pods container image slimmer to reduce the memory footprint.
  * See additional changes in [reana-cluster 0.5.0 release notes](https://reana-cluster.readthedocs.io/en/latest/changes.html#version-0-5-0-2019-04-24).

* Developers:

  * Enhances development process by using git-submodule-like behaviour for shared components.
  * Introduces simple Makefile for (fast) local testing and (slow) nightly building purposes.
  * Centralises logging level and common Celery tasks.
  * Adds helpers for test suite fixtures and improves code coverage.
  * See additional changes in [individual REANA 0.5.0 platform components](https://reana.readthedocs.io/en/latest/administratorguide.html#components).

## 0.4.0 (2018-11-07)

* Uses common OpenAPI client in communications between workflow engines and job
  controller.
* Improves AMQP re-connection handling.
* Enhances test suite and increases code coverage.
* Changes license to MIT.

## 0.3.0 (2018-09-27)

* Introduces new Serial workflow engine for simple sequential workflow needs.
* Enhances progress reporting for CWL, Serial and Yadage workflow engines.
* Simplifies `reana-client` command set and usage scenarios.
* Introduces multi-user capabilities with mandatory access tokens.
* Adds support for multi-node clusters using shared CephFS volumes.
* Adds support for Kubernetes 1.11, Minikube 0.28.2.
* Upgrades CWL workflow engine to use latest `cwltool` version.
* Fixes several bugs such as binary file download with Python 3.

## 0.2.0 (2018-04-23)

* Adds support for Common Workflow Language workflows.
* Adds support for persistent user-selected workflow names.
* Enables file and directory input uploading using absolute paths.
* Enriches `reana-client` and `reana-cluster` command set.
* Reduces verbosity level for commands and improves error messages.

## 0.1.0 (2018-01-30)

* Initial public release.
