# Some notes on tests


Package structure
-----------------

### Packages


* __local__

  Contains tests which run locally, i.e. run without ever making an internet
  connection. These tests are intended to be run frequently and to be used to 
  verify code changes. New code should be covered by new local tests. All
  local tests must pass.

* __support__

  Contains several support modules to setup tests, check results and other
  common utilities used in tests.

* __test_docs__

  Consists of various documents which are used as input for local tests. Most 
  documents are originally retrieved from the web, but some are edited to 
  provide the better test data. Simply overwriting test docs with new ones 
  obtained from the web may not only cause tests to fail, but also vital test 
  data being missed.

* __web__

  Tests which all make actual requests to the internet. These tests are used to
  verify the existence of end points and the data they return, and also to
  perform real life integration tests. Web test can be used to detect
  (breaking) changes at itv's web services, even before users report issues.


Running tests
-------------

### Dependencies
Dependencies available on pypi are in requirements.txt and should be easy to 
install. Other packages used by this addon, but not available on pypi are 
codequick and inputstreamhelper. This addon relies heavily on codequick, and 
it is best to download the full package from GitHub to your python environment.

You can easily create a stub for inputstreamhelper yourself. Create a file 
named inputstreamhelper.py with the following contents:

``` python
class Helper:
  inputstream_addon = None
  def __init__(self, protocol, drm):
      pass
  def check_inputstream(self):
      return True
```
Place the file in the site-packages folder of your (virtual) environment, or 
any other place on your pythonpath.


### Account credentials

A number of web tests require a user being signed in to itvX. Before each
test run with web tests an attempt is made to sign in with the user's 
credentials. Provide your credentials by copying the file 
`account_login.example`, rename it to `account_login.py` and replace the 
example username and password with your own. This file is already in .gitignore, 
so it should never end up on a public repository. Please ensure it stays that 
way and keep your credentials private.


### Profile directory

When tests are being run a directory named `addon_profile_dir` will be created 
under `test/`. This is the equivalent of the directory returned by 
`xbmcaddon.Addon().getAddonInfo('profile')` on a real Kodi system. This 
folder will contain files created during tests, amongst which is addon.log - 
the log file created on a test run. 
Web tests may rely on the presence of these files, local tests should not. 
The log file is cleared before each test run.


Creating new tests
------------------

The existing modules can be extended with new classes and methods based on 
python's unittest framework. 


Every test module should start with:

```python
from test.support import fixtures
fixtures.global_setup()
```

This will do some basic setup required to run tests, like monkey-patching 
kodi-stubs to return the above-mentioned profile directory. Place this 
before any other import, so all support libraries will take the patched version.


### Modules with local tests

Modules with local tests should include:
```python
setUpModule = fixtures.setup_local_tests
tearDownModule = fixtures.tear_down_local_tests
```
Define this at module level to ensure the python requests module does not 
inadvertently make real requests to the internet.


### Modules with web tests
Modules with web requests should include
```python
setUpModule = fixtures.setup_web_test
```
at module level when account login is required for the tests. Automatic sign-in 
is done only once per test run, so it's safe to add it to every web test module.
A manual sign-in can be done by calling support.fixtures.set_credentials(...).