// SPDX-License-Identifier: GPL-2.0-only
/* Native supervisor prototype. Default executable is DISARMED.
 * Only a host-test build exposes the fixture dispatcher. No shell, module
 * syscall, ADB, reset, timeout-kill or automatic recovery is implemented.
 */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include "sha256.h"

#define CAPTURE 65536
#define RECORD 190000
struct request {
    const char *path, *boot, *attempt, *operation, *action, *module, *mode;
    int root, lease, executable, control;
    uintmax_t root_dev, root_ino, lease_dev, lease_ino;
};
struct capture { unsigned char bytes[CAPTURE]; size_t length; int overflow; };
static volatile sig_atomic_t interrupted;
#ifdef Q3_SUPERVISOR_HOST_TEST
static int host_signal_fd=-1;
#endif
static void note_signal(int sig)
{
    int saved=errno;
    (void)sig; interrupted=1;
#ifdef Q3_SUPERVISOR_HOST_TEST
    if (host_signal_fd>=0) { ssize_t sent=write(host_signal_fd,"S\n",2); (void)sent; }
#endif
    errno=saved;
}
static void child_abort(int fd, int error)
{
    ssize_t sent;
    do { sent=write(fd,&error,sizeof(error)); } while (sent<0 && errno==EINTR);
    _exit(127);
}
static int hex_string(const char *s, size_t n)
{
    size_t i;
    if (strlen(s)!=n) return 0;
    for (i=0;i<n;i++) if (!((s[i]>='0' && s[i]<='9') || (s[i]>='a' && s[i]<='f'))) return 0;
    return 1;
}
static int boot_string(const char *s)
{
    size_t i;
    if (strlen(s)!=36) return 0;
    for (i=0;i<36;i++) {
        if (i==8 || i==13 || i==18 || i==23) { if (s[i]!='-') return 0; }
        else if (!((s[i]>='0' && s[i]<='9') || (s[i]>='a' && s[i]<='f'))) return 0;
    }
    return 1;
}
static int private_file(int fd)
{
    struct stat s;
    return fstat(fd,&s)==0 && S_ISREG(s.st_mode) && (s.st_mode&07777)==0600 &&
           s.st_uid==geteuid() && s.st_nlink==1;
}
static int same_root(const struct request *r)
{
    struct stat a,b,c,d;
    return fstat(r->root,&a)==0 && lstat(r->path,&b)==0 &&
           S_ISDIR(a.st_mode) && S_ISDIR(b.st_mode) && (a.st_mode&07777)==0700 &&
           a.st_uid==geteuid() && (uintmax_t)a.st_dev==r->root_dev && (uintmax_t)a.st_ino==r->root_ino &&
           a.st_dev==b.st_dev && a.st_ino==b.st_ino && private_file(r->lease) &&
           fstat(r->lease,&c)==0 && fstatat(r->root,"lease.lock",&d,AT_SYMLINK_NOFOLLOW)==0 &&
           S_ISREG(d.st_mode) && (uintmax_t)c.st_dev==r->lease_dev && (uintmax_t)c.st_ino==r->lease_ino &&
           c.st_dev==d.st_dev && c.st_ino==d.st_ino;
}
static int exact_record(int root, const char *name, const char *expected)
{
    char buffer[2048]; size_t used=0; ssize_t n; int result=-1;
    int fd=openat(root,name,O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
    if (fd<0) return -1;
    if (!private_file(fd)) goto out;
    while (used<sizeof(buffer)) {
        n=read(fd,buffer+used,sizeof(buffer)-used);
        if (n<0 && errno==EINTR) continue;
        if (n<0) goto out;
        if (!n) { result=(used==strlen(expected) && !memcmp(buffer,expected,used)) ? 0 : -1; goto out; }
        used+=(size_t)n;
    }
out:
    close(fd); return result;
}
static int check_claim(const struct request *r, char *intent, size_t capacity)
{
    char owner[1024], claim[2048], filename[64];
    struct dirent *entry; DIR *directory; int count=0, result=0, fd;
    int n=snprintf(intent,capacity,
        "{\"action_sha256\":\"%s\",\"attempt\":\"%s\",\"boot\":\"%s\",\"module_sha256\":\"%s\",\"operation\":\"%s\"}",
        r->action,r->attempt,r->boot,r->module,r->operation);
    if (n<0 || (size_t)n>=capacity) return -1;
    n=snprintf(owner,sizeof(owner),
        "{\"attempt\":\"%s\",\"boot\":\"%s\",\"lease_dev\":%ju,\"lease_ino\":%ju,\"module_sha256\":\"%s\",\"root_dev\":%ju,\"root_ino\":%ju,\"schema\":1}\n",
        r->attempt,r->boot,r->lease_dev,r->lease_ino,r->module,r->root_dev,r->root_ino);
    if (n<0 || (size_t)n>=sizeof(owner)) return -1;
    n=snprintf(claim,sizeof(claim),"{\"intent\":%s,\"schema\":1}\n",intent);
    if (n<0 || (size_t)n>=sizeof(claim)) return -1;
    if (snprintf(filename,sizeof(filename),"claim-%s.json",r->operation)!=43) return -1;
    if (exact_record(r->root,"owner.json",owner) || exact_record(r->root,filename,claim)) return -1;
    /* Deliberately one operation per prototype directory; no native catalogue
     * migration or session retirement is implemented. Reject everything else. */
    fd=openat(r->root,".",O_RDONLY|O_CLOEXEC|O_DIRECTORY);
    if (fd<0) return -1;
    directory=fdopendir(fd);
    if (!directory) { close(fd); return -1; }
    errno=0;
    while ((entry=readdir(directory))) {
        if (!strcmp(entry->d_name,".") || !strcmp(entry->d_name,"..")) continue;
        if (strcmp(entry->d_name,"lease.lock") && strcmp(entry->d_name,"owner.json") && strcmp(entry->d_name,filename)) result=-1;
        count++;
    }
    if (errno || count!=3) result=-1;
    closedir(directory); return result;
}
static int verify_action(const struct request *r)
{
    struct stat info; struct sha256_ctx s;
    unsigned char data[4096], binary[32], digest[32];
    char actual[65]; size_t i; ssize_t n;
    static const char digits[]="0123456789abcdef", domain[]="host-fixture-v1";
    if (fstat(r->executable,&info) || !S_ISREG(info.st_mode) || info.st_nlink!=1 ||
        info.st_uid!=geteuid() || (info.st_mode&022) || !(info.st_mode&S_IXUSR) ||
        info.st_size<4 || info.st_size>16*1024*1024 || lseek(r->executable,0,SEEK_SET)<0) return -1;
    sha256_init(&s);
    while ((n=read(r->executable,data,sizeof(data)))!=0) {
        if (n<0 && errno==EINTR) continue;
        if (n<0) return -1;
        sha256_update(&s,data,(size_t)n);
    }
    sha256_finish(&s,binary);
    if (pread(r->executable,data,4,0)!=4 || memcmp(data,"\177ELF",4)) return -1;
    sha256_init(&s); sha256_update(&s,domain,sizeof(domain));
    sha256_update(&s,r->mode,strlen(r->mode)+1); sha256_update(&s,binary,sizeof(binary)); sha256_finish(&s,digest);
    for (i=0;i<32;i++) { actual[2*i]=digits[digest[i]>>4]; actual[2*i+1]=digits[digest[i]&15]; } actual[64]=0;
    return strcmp(actual,r->action) ? -1 : 0;
}
static void encode64(const unsigned char *p, size_t n, char *out)
{
    static const char alphabet[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    size_t i,j=0;
    for (i=0;i<n;i+=3) {
        unsigned v=(unsigned)p[i]<<16;
        if (i+1<n) v|=(unsigned)p[i+1]<<8;
        if (i+2<n) v|=p[i+2];
        out[j++]=alphabet[v>>18]; out[j++]=alphabet[(v>>12)&63];
        out[j++]=i+1<n ? alphabet[(v>>6)&63] : '=';
        out[j++]=i+2<n ? alphabet[v&63] : '=';
    }
    out[j]=0;
}
static int publication_fault(const char *point)
{
#ifdef Q3_SUPERVISOR_HOST_TEST
    const char *requested=getenv("Q3_NATIVE_FAULT");
    if (requested && !strcmp(requested,point)) { errno=EIO; return 1; }
#else
    (void)point;
#endif
    return 0;
}
static int publish(const struct request *r, const char *receipt, size_t length)
{
    char stage[64], done[64]; int fd; size_t position=0; ssize_t n;
    if (!same_root(r)) return -1;
    if (snprintf(stage,sizeof(stage),"native-stage-%s.json",r->operation)!=50 ||
        snprintf(done,sizeof(done),"done-%s.json",r->operation)!=42) return -1;
    fd=openat(r->root,stage,O_CREAT|O_EXCL|O_WRONLY|O_CLOEXEC|O_NOFOLLOW,0600);
    if (fd<0) return -1;
    while (position<length) {
        n=write(fd,receipt+position,length-position);
        if (n<0 && errno==EINTR) continue;
        if (n<=0) { close(fd); return -1; }
        position+=(size_t)n;
    }
    if (publication_fault("file-fsync") || fsync(fd)) { close(fd); return -1; }
    if (close(fd) || publication_fault("link") || linkat(r->root,stage,r->root,done,0) ||
        publication_fault("directory-fsync") || fsync(r->root) || publication_fault("unlink") ||
        unlinkat(r->root,stage,0) || publication_fault("final-fsync") || fsync(r->root)) return -1;
    return 0;
}
static int close_list(int *list, size_t *count)
{
    DIR *d=opendir("/proc/self/fd"); struct dirent *entry;
    if (!d) return -1;
    *count=0;
    while ((entry=readdir(d))) {
        char *end; long fd;
        errno=0; fd=strtol(entry->d_name,&end,10);
        if (errno || *end || fd<3 || fd==dirfd(d)) continue;
        if (*count==256 || fd>INT_MAX) { closedir(d); return -1; }
        list[(*count)++]=(int)fd;
    }
    closedir(d); return 0;
}
/* Single-threaded core; a future Android dispatcher must validate current boot,
 * action policy and canonical session roots before invoking any action. */
int q3_supervise_fixture(const struct request *r)
{
    int pipes[3][2], list[256], status=0, exec_error=0, io_error=0, live=3;
    size_t count=0, i, error_bytes=0; pid_t child, waited;
    struct capture *output=NULL; struct pollfd fds[3];
    char intent[512], control[24], *b64out=NULL,*b64err=NULL,*receipt=NULL, oh[65],eh[65];
    struct sigaction action; sigset_t empty; int result=74, value, n; const char *kind;
    if (!boot_string(r->boot) || !hex_string(r->attempt,32) || !hex_string(r->operation,32) ||
        !hex_string(r->action,64) || !hex_string(r->module,64) || strlen(r->mode)>24 ||
        strspn(r->mode,"abcdefghijklmnopqrstuvwxyz-")!=strlen(r->mode) || !strlen(r->mode) ||
        r->root<3 || r->lease<3 || r->executable<3 || r->root==r->lease ||
        r->executable==r->root || r->executable==r->lease ||
        (r->control!=-1 && (r->control<3 || r->control==r->root || r->control==r->lease || r->control==r->executable))) return 77;
    if (!same_root(r) || flock(r->lease,LOCK_EX|LOCK_NB) || check_claim(r,intent,sizeof(intent)) || verify_action(r)) return 77;
#ifdef Q3_SUPERVISOR_HOST_TEST
    host_signal_fd=r->control;
#endif
    memset(&action,0,sizeof(action)); sigemptyset(&action.sa_mask); action.sa_handler=note_signal;
    if (sigaction(SIGINT,&action,NULL) || sigaction(SIGTERM,&action,NULL) || sigaction(SIGHUP,&action,NULL)) return 74;
    action.sa_handler=SIG_IGN;
    if (sigaction(SIGPIPE,&action,NULL)) return 74;
    sigemptyset(&empty);
    if (sigprocmask(SIG_SETMASK,&empty,NULL)) return 74;
    output=calloc(2,sizeof(*output));
    if (!output) return 74;
    for (i=0;i<3;i++) {
        if (pipe2(pipes[i],O_CLOEXEC)) { while (i) { i--; close(pipes[i][0]); close(pipes[i][1]); } free(output); return 74; }
    }
    for (i=0;i<3;i++) if (fcntl(pipes[i][0],F_SETFL,O_NONBLOCK)<0) goto before_fork;
    if (close_list(list,&count)) goto before_fork;
    child=fork();
    if (child<0) goto before_fork;
    if (!child) {
        char *argv[4], *environment[]={"PATH=/nonexistent",NULL}; int nullfd;
        struct sigaction reset;
        memset(&reset,0,sizeof(reset)); reset.sa_handler=SIG_DFL; sigemptyset(&reset.sa_mask);
        if (sigaction(SIGINT,&reset,NULL) || sigaction(SIGTERM,&reset,NULL) ||
            sigaction(SIGHUP,&reset,NULL) || sigaction(SIGPIPE,&reset,NULL) ||
            sigprocmask(SIG_SETMASK,&empty,NULL)) child_abort(pipes[2][1],errno);
        for (i=0;i<count;i++) if (list[i]!=r->lease && list[i]!=r->executable && list[i]!=r->control &&
                list[i]!=pipes[0][1] && list[i]!=pipes[1][1] && list[i]!=pipes[2][1]) close(list[i]);
        nullfd=open("/dev/null",O_RDONLY);
        if (nullfd<0 || dup2(nullfd,0)<0 || dup2(pipes[0][1],1)<0 || dup2(pipes[1][1],2)<0 ||
            fcntl(r->lease,F_SETFD,0)<0 || fcntl(r->executable,F_SETFD,FD_CLOEXEC)<0) {
            child_abort(pipes[2][1],errno);
        }
        if (nullfd>2) close(nullfd);
        close(pipes[0][1]); close(pipes[1][1]);
        snprintf(control,sizeof(control),"%d",r->control);
        argv[0]="q3-host-fixture"; argv[1]=(char *)r->mode; argv[2]=control; argv[3]=NULL;
        fexecve(r->executable,argv,environment);
        child_abort(pipes[2][1],errno);
    }
    for (i=0;i<3;i++) {
        close(pipes[i][1]); fds[i]=(struct pollfd){pipes[i][0],POLLIN,0};
    }
    while (live) {
        unsigned char bytes[4096]; ssize_t got;
        n=poll(fds,3,-1);
        if (n<0 && errno==EINTR) continue;
        if (n<0) { io_error=1; break; }
        for (i=0;i<3;i++) if (fds[i].fd>=0 && fds[i].revents) {
            do {
                got=read(fds[i].fd,bytes,sizeof(bytes));
                if (got>0 && i<2) {
                    size_t take=(size_t)got;
                    if (take>CAPTURE-output[i].length) { take=CAPTURE-output[i].length; output[i].overflow=1; }
                    memcpy(output[i].bytes+output[i].length,bytes,take); output[i].length+=take;
                } else if (got>0) {
                    if ((size_t)got>sizeof(exec_error)-error_bytes) io_error=1;
                    else { memcpy((char *)&exec_error+error_bytes,bytes,(size_t)got); error_bytes+=(size_t)got; }
                }
            } while (got>0 || (got<0 && errno==EINTR));
            if (got==0 || (got<0 && errno!=EAGAIN && errno!=EWOULDBLOCK)) {
                if (got<0) io_error=1;
                close(fds[i].fd); fds[i].fd=-1; live--;
            }
        }
    }
    for (i=0;i<3;i++) if (fds[i].fd>=0) close(fds[i].fd);
    do { waited=waitpid(child,&status,0); } while (waited<0 && errno==EINTR);
    if (waited!=child || io_error || output[0].overflow || output[1].overflow ||
        (error_bytes && error_bytes!=sizeof(exec_error)) || exec_error<0 || exec_error>4095) goto out;
    if (WIFEXITED(status)) { kind="exit"; value=WEXITSTATUS(status); }
    else if (WIFSIGNALED(status)) { kind="signal"; value=WTERMSIG(status); }
    else goto out;
    b64out=malloc(4*((CAPTURE+2)/3)+1); b64err=malloc(4*((CAPTURE+2)/3)+1); receipt=malloc(RECORD);
    if (!b64out || !b64err || !receipt) goto out;
    encode64(output[0].bytes,output[0].length,b64out); encode64(output[1].bytes,output[1].length,b64err);
    sha256_hex(output[0].bytes,output[0].length,oh); sha256_hex(output[1].bytes,output[1].length,eh);
    n=snprintf(receipt,RECORD,
        "{\"schema\":2,\"intent\":%s,\"foreground_reaped\":true,\"termination_kind\":\"%s\",\"termination_value\":%d,\"exec_errno\":%d,\"supervisor_interrupted\":%s,"
        "\"stdout_b64\":\"%s\",\"stdout_size\":%zu,\"stdout_sha256\":\"%s\",\"stderr_b64\":\"%s\",\"stderr_size\":%zu,\"stderr_sha256\":\"%s\","
        "\"tree_quiescence_proven\":false,\"safe_to_mutate\":false}\n",
        intent,kind,value,exec_error,interrupted ? "true" : "false",b64out,output[0].length,oh,b64err,output[1].length,eh);
    if (n<0 || n>=RECORD || publish(r,receipt,(size_t)n)) goto out;
    { char reply[80]; int length=snprintf(reply,sizeof(reply),"ERIS_NATIVE_RECEIPT %s\n",r->operation);
      ssize_t written; do { written=write(1,reply,(size_t)length); } while (written<0 && errno==EINTR);
      result=written==length ? 0 : 74; }
out:
    free(receipt); free(b64err); free(b64out); free(output); return result;
before_fork:
    for (i=0;i<3;i++) { close(pipes[i][0]); close(pipes[i][1]); }
    free(output); return 74;
}

#ifdef Q3_SUPERVISOR_HOST_TEST
static uintmax_t number(const char *s)
{
    char *end; uintmax_t value;
    if (!*s || strspn(s,"0123456789")!=strlen(s)) exit(77);
    errno=0; value=strtoumax(s,&end,10); if (errno || *end) exit(77); return value;
}
int main(int argc, char **argv)
{
    struct request r; uintmax_t root,lease,executable,control;
    if (argc!=17 || strcmp(argv[1],"--host-fixture")) return 77;
    root=number(argv[3]); lease=number(argv[4]); executable=number(argv[5]);
    control=!strcmp(argv[16],"-1") ? 0 : number(argv[16]);
    if (root>INT_MAX || lease>INT_MAX || executable>INT_MAX || control>INT_MAX) return 77;
    r=(struct request){argv[2],argv[10],argv[11],argv[12],argv[13],argv[14],argv[15],
        (int)root,(int)lease,(int)executable,control ? (int)control : -1,
        number(argv[6]),number(argv[7]),number(argv[8]),number(argv[9])};
    return q3_supervise_fixture(&r);
}
#else
int main(void)
{
    static const char message[]="Disarmed native prototype: no Android/device dispatcher enabled.\n";
    ssize_t sent=write(2,message,sizeof(message)-1); (void)sent; return 77;
}
#endif
