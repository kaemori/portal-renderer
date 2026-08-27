import keyboard
import subprocess

# evil shit
keyboard._nixkeyboard.ensure_root = lambda: 0
keyboard._nixkeyboard.check_output = lambda cmd, **kwargs: (
    subprocess.check_output(["dumpkeys", "-C", "/dev/tty1"] + cmd[1:], **kwargs)
    if cmd[0] == "dumpkeys"
    else subprocess.check_output(cmd, **kwargs)
)

if __name__ == "__main__":
    keyboard.wait("k")
