# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3-slim-trixie

RUN apt-get update && \
  apt-get install -yq --no-install-suggests --no-install-recommends curl git ca-certificates && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  git config --system init.defaultBranch main

WORKDIR /app

RUN python3 -m venv venv
RUN ./venv/bin/pip install requests PyYAML google-auth argcomplete secops
ENV VIRTUAL_ENV="/app/venv"
ENV PATH="/app/venv/bin:$PATH"

RUN curl -sSfL -o /usr/bin/download-secure-files \
  https://gitlab.com/gitlab-org/incubation-engineering/mobile-devops/download-secure-files/-/releases/permalink/latest/downloads/download-secure-files-linux-amd64 && \
  chmod +x /usr/bin/download-secure-files
