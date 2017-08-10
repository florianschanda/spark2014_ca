#!/usr/bin/env python
##############################################################################
##                                                                          ##
##                             spark2014_ca                                 ##
##                                                                          ##
##              Copyright (C) 2017, Altran UK Limited                       ##
##                                                                          ##
##  This file is part of the SPARK 2014 continous analysis project.         ##
##                                                                          ##
##  spark2014_ca is free software: you can redistribute it and/or modify    ##
##  it under the terms of the GNU General Public License as published by    ##
##  the Free Software Foundation, either version 3 of the License, or       ##
##  (at your option) any later version.                                     ##
##                                                                          ##
##  spark2014_ca is distributed in the hope that it will be useful,         ##
##  but WITHOUT ANY WARRANTY; without even the implied warranty of          ##
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           ##
##  GNU General Public License for more details.                            ##
##                                                                          ##
##  You should have received a copy of the GNU General Public License       ##
##  along with spark20214_ca. If not, see <http://www.gnu.org/licenses/>.   ##
##                                                                          ##
##############################################################################

# This script scans the CVC4 repository for new revisions and attempts to
# build every single one after a certain date.

import os
import subprocess
import multiprocessing

CVC4_MAIN_REPOSITORY = "http://github.com/CVC4/cvc4.git"

# Do not consider any commits before this day
FIRST_DATE = "2017-07-01"

ROOT_DIR = os.getcwd()

LIBRARY_DIR = os.path.join(ROOT_DIR, "cvc4_binaries")

STATUS_FILE = os.path.join(LIBRARY_DIR, "status.txt")

BUILD_ENV = {
    "PATH"               : "/bin:/usr/bin",
    "C_INCLUDE_PATH"     : "/usr/include/x86_64-linux-gnu",
    "CPLUS_INCLDUE_PATH" : "/usr/include/x86_64-linux-gnu",
    "LIBRARY_PATH"       : "/usr/lib/x86_64-linux-gnu",
}

def update_repo():
    os.chdir(ROOT_DIR)

    if not os.path.exists("cvc4"):
        os.system("git clone %s cvc4" % CVC4_MAIN_REPOSITORY)

    os.chdir("cvc4")
    os.system("git reset --hard master")
    os.system("git checkout master")
    os.system("git clean -xdfq")
    os.system("git pull --rebase")

def get_revisions():
    os.chdir(ROOT_DIR)
    os.chdir("cvc4")

    p = subprocess.Popen(["git",
                          "log",
                          "--since=%s" % FIRST_DATE,
                          "--format=oneline"],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    log, _ = p.communicate()

    rv = []
    for line in log.splitlines():
        sha = line.split()[0]
        assert set(sha) <= set("0123456789abcdef")
        rv.append(sha)
    rv.reverse()

    return rv

def build_revision(sha):
    os.chdir(ROOT_DIR)
    os.chdir("cvc4")

    os.system("git checkout -- .")
    os.system("git checkout %s" % sha)
    os.system("git clean -xdfq")

    print "Preparing build %s" % sha
    p = subprocess.Popen(["./autogen.sh"],
                         stdin = subprocess.PIPE,
                         stdout = subprocess.PIPE,
                         stderr = subprocess.STDOUT,
                         env = BUILD_ENV)
    out, _ = p.communicate()
    ok = (p.returncode == 0)

    if ok:
        print "Configuring build %s" % sha
        p = subprocess.Popen(["./configure",
                              "--disable-maintainer-mode",
                              "--enable-shared=no",
                              "--disable-dependency-tracking",
                              "--disable-proof",
                              "--enable-optimized",
                              "--disable-debug-symbols",
                              "--disable-replay",
                              "--disable-doxygen-doc",
                              "--disable-doxygen-html",
                              "--disable-unit-testing",
                              "--disable-thread-support",
                              "--with-gmp"],
                             stdin = subprocess.PIPE,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.STDOUT,
                             env = BUILD_ENV)
        out, _ = p.communicate()
        ok = (p.returncode == 0)

    if ok:
        print "Building %s" % sha
        p = subprocess.Popen(["make", "-j", str(multiprocessing.cpu_count())],
                             stdin = subprocess.PIPE,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.STDOUT,
                             env = BUILD_ENV)
        out, _ = p.communicate()
        ok = (p.returncode == 0)

    if ok:
        print "Installing %s" % sha
        src = None
        dst = os.path.join(LIBRARY_DIR, "cvc4_%s" % sha)
        for path, dirs, files in os.walk("builds"):
            if "cvc4" in files:
                src = os.path.join(path, "cvc4")
                if not os.path.islink(src):
                    break
        assert src is not None
        os.rename(src, dst)
        os.system("strip -s %s" % dst)

    return ok

def main():
    update_repo()
    rev_list = get_revisions()
    status = {}

    if not os.path.exists(LIBRARY_DIR):
        os.mkdir(LIBRARY_DIR)

    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "rU") as fd:
            for raw_line in fd:
                sha, build_status = raw_line.strip().split()
                if sha in rev_list:
                    status[sha] = build_status
                elif build_status == "ok":
                    # This previously built binary is no longer in our
                    # revision list we care about.
                    os.unlink(os.path.join(LIBRARY_DIR,
                                           "cvc4_%s" % sha))

    for rev in rev_list:
        if rev in status and status[rev] == "error":
            print "Skipping %s (remembered build error)" % rev
        elif os.path.exists(os.path.join(LIBRARY_DIR,
                                         "cvc4_%s" % rev)):
            print "Skipping %s (already built)" % rev
            status[rev] = "ok"
        else:
            status[rev] = "ok" if build_revision(rev) else "error"

    with open(STATUS_FILE, "w") as fd:
        for rev in rev_list:
            fd.write("%s %s\n" % (rev, status[rev]))

if __name__ == "__main__":
    main()
