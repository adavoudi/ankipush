FROM debian:12.4-slim

ARG ANKI_VERSION=25.02.4
ARG QT_VERSION=6

RUN apt update && apt install --no-install-recommends -y \
        wget zstd mpv locales curl git ca-certificates jq libxcb-xinerama0 libxcb-cursor0 libnss3 \
        libxcomposite-dev libxdamage-dev libxtst-dev libxkbcommon-dev libxkbfile-dev
RUN useradd -m anki

# Anki installation
RUN mkdir /app && chown -R anki:anki /app
COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh
WORKDIR /app

RUN wget -O ANKI.tar.zst --no-check-certificate https://github.com/ankitects/anki/releases/download/${ANKI_VERSION}/anki-${ANKI_VERSION}-linux-qt${QT_VERSION}.tar.zst && \
    zstd -d ANKI.tar.zst && rm ANKI.tar.zst && \
    tar xfv ANKI.tar && rm ANKI.tar
WORKDIR /app/anki-${ANKI_VERSION}-linux-qt${QT_VERSION}

RUN cat install.sh | sed 's/xdg-mime/#/' | sh -

RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8 LANGUAGE=en_US LC_ALL=en_US.UTF-8

RUN apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /data/addons21 /export && chown -R anki:anki /data /export
# Pre-seed a default profile so Anki skips the first-run setup wizard
ADD data /data
RUN chown -R anki:anki /data
VOLUME /data
VOLUME /export

# Copy addon into staging area
WORKDIR /app
COPY --chown=anki:anki addon /app/addon

USER anki

ENV QMLSCENE_DEVICE=softwarecontext
ENV FONTCONFIG_PATH=/etc/fonts
ENV QT_XKB_CONFIG_ROOT=/usr/share/X11/xkb
ENV QT_QPA_PLATFORM="vnc"
ENV PYTHONUNBUFFERED=1

CMD ["/bin/bash", "/app/startup.sh"]
