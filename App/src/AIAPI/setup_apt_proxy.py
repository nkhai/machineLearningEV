import subprocess
content = 'Acquire::http::Proxy "http://vkn1hc:Tramvang%401216@10.187.197.10:8080";\nAcquire::https::Proxy "http://vkn1hc:Tramvang%401216@10.187.197.10:8080";\n'
with open("/tmp/apt-proxy.conf", "w") as f:
    f.write(content)
subprocess.run(["sudo", "cp", "/tmp/apt-proxy.conf", "/etc/apt/apt.conf.d/proxy.conf"], check=True)
print("Proxy config written to /etc/apt/apt.conf.d/proxy.conf")
