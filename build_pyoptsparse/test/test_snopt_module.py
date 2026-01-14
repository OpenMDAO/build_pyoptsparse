
# Standard Python modules
import unittest


class TestSNOPTModule(unittest.TestCase):

    def setUp(self) -> None:
        import subprocess
        import os
        import sys
        from pathlib import Path

        # Check if SNOPT module is already available
        try:
            from pyoptsparse import SNOPT
            print("SNOPT module already installed, skipping build")
            return
        except ImportError:
            print("SNOPT module not found, building...")

        try:
            src_path = Path(os.environ['SNOPT_SRC_PATH'])
        except KeyError:
            raise RuntimeError('This test requires environment variable SNOPT_SRC_PATH be set.')

        if not src_path.exists():
            raise FileNotFoundError(f"Source path not found: {src_path}")

        try:
            subprocess.run(
                [sys.executable, "-m", "build_pyoptsparse.snopt_module", str(src_path)],
                check=True,
                capture_output=True,
                text=True
            )

        except subprocess.CalledProcessError as e:
            print(f"Build failed with return code {e.returncode}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            raise

    def test_hs071(self):
        import numpy as np
        from numpy.testing import assert_almost_equal
        from pyoptsparse import OPT, Optimization

        def objfunc(xdict):
            x = xdict["xvars"]
            funcs = {}
            funcs["obj"] = x[0] * x[3] * (x[0] + x[1] + x[2]) + x[2]
            funcs["con1"] = x[0] * x[1] * x[2] * x[3]
            funcs["con2"] = x[0] * x[0] + x[1] * x[1] + x[2] * x[2] + x[3] * x[3]
            fail = False
            return funcs, fail

        def sens(xdict, funcs):
            x = xdict["xvars"]
            funcsSens = {}
            funcsSens["obj"] = {
                "xvars": np.array(
                    [x[0] * x[3] + x[3] * (x[0] + x[1] + x[2]), x[0] * x[3], x[0] * x[3] + 1.0, x[0] * (x[0] + x[1] + x[2])]
                )
            }
            jac = [[x[1] * x[2] * x[3], x[0] * x[2] * x[3], x[0] * x[1] * x[3], x[0] * x[1] * x[2]]]
            funcsSens["con1"] = {"xvars": jac}
            jac = [[2.0 * x[0], 2.0 * x[1], 2.0 * x[2], 2.0 * x[3]]]
            funcsSens["con2"] = {"xvars": jac}
            fail = False
            return funcsSens, fail

        # Optimization Object
        optProb = Optimization("HS071 Constraint Problem", objfunc)

        # Design Variables
        x0 = [1.0, 5.0, 5.0, 1.0]
        optProb.addVarGroup("xvars", 4, lower=1, upper=5, value=x0)

        # Constraints
        # optProb.addCon('con1', lower=25, upper=1e19)
        optProb.addCon("con1", lower=25)
        # optProb.addCon('con2', lower=40, upper=40)
        optProb.addCon("con2", lower=40, upper=40)

        # Objective
        optProb.addObj("obj")

        # Check optimization problem:
        print(optProb)

        # Optimizer
        opt = OPT('SNOPT')

        # Solution
        sol = opt(optProb, sens=sens)

        self.assertEqual(sol.optInform.value, 1)


if __name__ == '__main__':
    unittest.main()
