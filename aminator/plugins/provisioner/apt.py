# -*- coding: utf-8 -*-

#
#
#  Copyright 2013 Netflix, Inc.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
#

"""
aminator.plugins.provisioner.apt
================================
basic apt provisioner
"""
import logging
import os

from aminator.plugins.provisioner.base import BaseProvisionerPlugin
from aminator.util.linux import command, keyval_parse

__all__ = ('AptProvisionerPlugin',)
log = logging.getLogger(__name__)


class AptProvisionerPlugin(BaseProvisionerPlugin):
    """
    AptProvisionerPlugin takes the majority of its behavior from BaseProvisionerPlugin
    See BaseProvisionerPlugin for details
    """
    _name = 'apt'

    def _refresh_repo_metadata(self):
        return self.apt_get_update()

    def _provision_package(self):
        result = self._refresh_repo_metadata()
        if not result.success: # pylint: disable=no-member
            log.critical('Repo metadata refresh failed: {0.std_err}'.format(result)) # pylint: disable=no-member
            return False
        context = self._config.context
        os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
        if context.package.get('local_install', False):
            return self.apt_get_localinstall(context.package.arg)
        else:
            return self.apt_get_install(context.package.arg)

    def _store_package_metadata(self):
        context = self._config.context
        config = self._config.plugins[self.full_name]
        metadata = self.deb_package_metadata(context.package.arg, config.get('pkg_query_format', ''), context.package.get('local_install', False))
        for x in config.pkg_attributes:
            if x == 'version' and x in metadata:
                if ':' in metadata[x]:
                    # strip epoch element from version
                    vers = metadata[x]
                    metadata[x] = vers[vers.index(':')+1:]
                if '-' in metadata[x]:
                    # debs include release in version so split
                    # version into version-release to compat w/rpm
                    vers, rel = metadata[x].split('-', 1)
                    metadata[x] = vers
                    metadata['release'] = rel
                else:
                    metadata['release'] = 0
                # this is probably not necessary given above
            metadata.setdefault(x, None)
        context.package.attributes = metadata

    @staticmethod
    @command()
    def dpkg_install(package):
        return 'dpkg -i {0}'.format(package)
    
    @classmethod
    def apt_get_localinstall(cls, package):
        """install deb file with dpkg then resolve dependencies
        """
        dpkg_ret = cls.dpkg_install(package)
        if not dpkg_ret.success:
            log.debug('failure:{0.command} :{0.std_err}'.format(dpkg_ret))
            apt_ret = cls.apt_get_install('--fix-missing')
            if not apt_ret.success:
                log.debug('failure:{0.command} :{0.std_err}'.format(apt_ret))
            return apt_ret
        return dpkg_ret
    
    @staticmethod
    @command()
    def deb_query(package, queryformat, local=False):
        if local:
            cmd = 'dpkg-deb -W'.split()
            cmd.append('--showformat={0}'.format(queryformat))
        else:
            cmd = 'dpkg-query -W'.split()
            cmd.append('-f={0}'.format(queryformat))
        cmd.append(package)
        return cmd
    

    @staticmethod
    @command()
    def apt_get_update():
        return 'apt-get update'
    
    @classmethod
    @command()
    def apt_get_install(cls, package):
        return 'apt-get -y install {0}'.format(package)
    
    @classmethod
    @keyval_parse()
    def deb_package_metadata(cls, package, queryformat, local=False):
        return cls.deb_query(package, queryformat, local)
