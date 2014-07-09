//
// dpty
//
// Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
//
// Stupid little pty program that gets a pty name so that a human can
// pretend to be an industrial robot for the purposes of validating
// ptyhon code written to talk to the robot.
//
#define _XOPEN_SOURCE
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/select.h>
#include <fcntl.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BUFSIZE 1024                // XXX arbitrary limit

int
main(int ac, char *av[])
{
    int pty_fd;
    int std_fd = fileno(stdin);
    int slv_fd;
    char *slave;
    int nfds;
    fd_set fds_template;
    int cnt;
    char buf[BUFSIZE];

    if ((pty_fd = open("/dev/ptmx", O_RDWR)) == -1) {
        perror("open(master)");
        exit(1);
    }

    if (grantpt(pty_fd)) {
        perror("grantpt");
        exit(2);
    }

    if (unlockpt(pty_fd)) {
        perror("unlockpt");
        exit(3);
    }

    if ((slave = ptsname(pty_fd)) == NULL) {
        perror("ptsname");
        exit(4);
    }

    //
    // Open the slave so that repeated intermittent operations on the
    // other end by robot scriopts do not result in the slave have a
    // close of its controlling tty resulting in signallling an EOF
    // as an I/O error on the read(2) call on the master.
    //
    if ((slv_fd = open(slave, O_RDWR)) == -1) {
        perror("open(slave)");
        exit(5);
    }

    //
    // Informational message so the human can communicate the "serial"
    // port name to the robot control script.  Use stderr in case we
    // want to redirect stdin/stdout at some point.
    //
    fprintf(stderr, "Waiting for I/O on slave '%s'\n", slave);

    // nonblocking I/O to make reads easier
    if (fcntl(pty_fd, F_SETFL, O_NONBLOCK)) {
        perror("pty_fd = O_NONBLOCK");
        exit(6);
    }
    if (fcntl(std_fd, F_SETFL, O_NONBLOCK)) {
        perror("pty_fd = O_NONBLOCK");
        exit(7);
    }

    // set up descriptor template
    FD_ZERO(&fds_template);
    FD_SET(std_fd, &fds_template);
    FD_SET(pty_fd, &fds_template);
    nfds = std_fd;
    if (nfds < pty_fd)
        nfds = pty_fd;
    nfds++;

    //
    // Select loop
    //
    for(;;) {
        fd_set fds;

        // reset each time through to keep select happy
        memcpy(&fds, &fds_template, sizeof(fds));

        fprintf(stderr, "Waiting for robot input\n");
        if (select(nfds, &fds, NULL, NULL, NULL) < 1)
            break;  // error/EOF/signal

        // ROBOT -> HUMAN
        if (FD_ISSET(pty_fd, &fds)) {
            if ((cnt = read(pty_fd, buf, BUFSIZE)) < 1) {
                // EOF or error
                perror("pty_fd: read");
                break;
            }
            write(fileno(stdout), buf, cnt);
        }

        // HUMAN -> ROBOT
        if (FD_ISSET(std_fd, &fds)) {
            if ((cnt = read(std_fd, buf, BUFSIZE)) < 1) {
                // EOF or error
                perror("std_fd: read");
                break;
            }
            write(pty_fd, buf, cnt);
        }
    }

    //
    // If we fall out, it's because select had nothing ready, but
    // returned anyway; we'll treat it like it's on purpose.
    //
    close(pty_fd);
    close(slv_fd);
    if (fcntl(std_fd, F_SETFL, O_NONBLOCK)) {
        perror("std_fd = O_NONBLOCK");
        fprintf(stderr, "You will need to reset your terminal mode\n");
    }
    fprintf(stderr, "Done!\n");

    exit(0);
}
