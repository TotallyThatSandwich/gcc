git -C /home/user/gcc-server pull 2>&1 | tee /tmp/gcc-server-pull.log
if [ $? -ne 0 ]; then
  curl -d @/tmp/gcc-server-pull.log ntfy.genericcursed.com/cron
fi
