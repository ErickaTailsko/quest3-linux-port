// SPDX-License-Identifier: GPL-2.0-only
/* Metadata-only native bootstrap reference. Default main is DISARMED.
 * Host-test CLI only: no activation, action claim, module, exec or transport.
 */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#include "sha256.h"

#define ROOT_NAME "q3-identity-registry"
#define PROFILE "q3-bootstrap-host-reference-v1"
struct bootstrap_request {
    const char *parent_path, *boot, *attempt, *operation, *device, *helper, *module;
    const char *authorization, *local_intent, *request_sha256;
    int parent, control;
    uintmax_t parent_dev, parent_ino;
};
struct bootstrap_pins { struct stat root, lease; };

static int hexadecimal(const char *text, size_t size)
{
    size_t i;
    if (strlen(text)!=size) return 0;
    for (i=0;i<size;i++) if (!((text[i]>='0' && text[i]<='9') || (text[i]>='a' && text[i]<='f'))) return 0;
    return 1;
}
static int boot_identity(const char *text)
{
    size_t i;
    if (strlen(text)!=36) return 0;
    for (i=0;i<36;i++) {
        if (i==8 || i==13 || i==18 || i==23) { if (text[i]!='-') return 0; }
        else if (!((text[i]>='0' && text[i]<='9') || (text[i]>='a' && text[i]<='f'))) return 0;
    }
    return 1;
}
static int private_object(const struct stat *s, int directory)
{
    return (directory ? S_ISDIR(s->st_mode) : S_ISREG(s->st_mode)) &&
        (s->st_mode&07777)==(directory ? 0700 : 0600) && s->st_uid==geteuid() &&
        (directory || s->st_nlink==1);
}
static int same_identity(const struct stat *a, const struct stat *b)
{
    return a->st_dev==b->st_dev && a->st_ino==b->st_ino;
}
static int parent_matches(const struct bootstrap_request *r)
{
    struct stat fd,path;
    return fstat(r->parent,&fd)==0 && lstat(r->parent_path,&path)==0 &&
        private_object(&fd,1) && private_object(&path,1) && same_identity(&fd,&path) &&
        (uintmax_t)fd.st_dev==r->parent_dev && (uintmax_t)fd.st_ino==r->parent_ino;
}
static int pins_match(const struct bootstrap_request *r, int root, int lease, const struct bootstrap_pins *pins)
{
    struct stat a,b;
    if (!parent_matches(r) || fstat(root,&a) || !private_object(&a,1) || !same_identity(&a,&pins->root) ||
        (uintmax_t)a.st_dev!=r->parent_dev ||
        fstatat(r->parent,ROOT_NAME,&b,AT_SYMLINK_NOFOLLOW) || !private_object(&b,1) || !same_identity(&a,&b)) return 0;
    if (lease>=0 && (fstat(lease,&a) || !private_object(&a,0) || !same_identity(&a,&pins->lease) ||
        fstatat(root,"lease.lock",&b,AT_SYMLINK_NOFOLLOW) || !private_object(&b,0) || !same_identity(&a,&b))) return 0;
    return 1;
}
static int catalogue(int root, unsigned expected)
{
    static const char *const names[]={"lease.lock","bootstrap-intent.json","bootstrap-receipt.json"};
    DIR *directory; struct dirent *entry; unsigned count=0,i; int error=0;
    int fd=openat(root,".",O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW);
    if (fd<0) return -1;
    directory=fdopendir(fd); if (!directory) { close(fd); return -1; }
    errno=0;
    while ((entry=readdir(directory))) {
        if (!strcmp(entry->d_name,".") || !strcmp(entry->d_name,"..")) continue;
        for (i=0;i<expected;i++) if (!strcmp(entry->d_name,names[i])) break;
        if (i==expected) error=1;
        if (++count>3) { error=1; break; }
    }
    if (errno || count!=expected) error=1;
    closedir(directory); return error ? -1 : 0;
}
static int test_point(const struct bootstrap_request *r, const char *point)
{
#ifdef Q3_BOOTSTRAP_HOST_TEST
    const char *fault=getenv("Q3_BOOTSTRAP_FAULT"), *pause=getenv("Q3_BOOTSTRAP_PAUSE");
    if (fault && !strcmp(fault,point)) { errno=EIO; return -1; }
    if (pause && !strcmp(pause,point)) {
        char value; ssize_t done;
        if (r->control<3 || write(r->control,"R\n",2)!=2) return -1;
        do { done=read(r->control,&value,1); } while (done<0 && errno==EINTR);
        if (done!=1 || value!='X') return -1;
    }
#else
    (void)r; (void)point;
#endif
    return 0;
}
static int named_point(const struct bootstrap_request *r, const char *record, const char *phase)
{
    char point[64]; int n=snprintf(point,sizeof(point),"%s-%s",record,phase);
    return n<0 || (size_t)n>=sizeof(point) ? -1 : test_point(r,point);
}
static int publish(const struct bootstrap_request *r, int root, int lease,
                   const struct bootstrap_pins *pins, const char *record, const char *data, size_t size)
{
    char pending[64],final[64]; size_t used=0; ssize_t wrote; int fd;
    if (!pins_match(r,root,lease,pins)) return -1;
    if (snprintf(pending,sizeof(pending),"bootstrap-%s.pending",record)<0 ||
        snprintf(final,sizeof(final),"bootstrap-%s.json",record)<0) return -1;
    fd=openat(root,pending,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);
    if (fd<0) return -1;
    while (used<size) {
        wrote=write(fd,data+used,size-used);
        if (wrote<0 && errno==EINTR) continue;
        if (wrote<=0) { close(fd); return -1; }
        used+=(size_t)wrote;
    }
    if (named_point(r,record,"file-fsync") || fsync(fd)) { close(fd); return -1; }
    if (close(fd) || named_point(r,record,"link") || linkat(root,pending,root,final,0) ||
        named_point(r,record,"directory-fsync") || fsync(root) || named_point(r,record,"unlink") ||
        unlinkat(root,pending,0) || named_point(r,record,"final-fsync") || fsync(root)) return -1;
    return pins_match(r,root,lease,pins) ? 0 : -1;
}
int q3_bootstrap_metadata_reference(const struct bootstrap_request *r)
{
    char request[2048],receipt[4096],commitment[65],reply[160];
    static const char domain[]="ERIS-Q3-BOOTSTRAP-HOST-V1";
    struct sha256_ctx sha; unsigned char digest[32]; static const char digits[]="0123456789abcdef";
    struct bootstrap_pins pins; struct stat entry; struct sigaction action;
    size_t i,position; ssize_t wrote; int n,root=-1,lease=-1,result=74;
    if (r->parent<3 || (r->control!=-1 && (r->control<3 || r->control==r->parent)) ||
        !boot_identity(r->boot) || !hexadecimal(r->attempt,32) || !hexadecimal(r->operation,32) ||
        !strcmp(r->attempt,r->operation) || !hexadecimal(r->device,64) || !hexadecimal(r->helper,64) ||
        !hexadecimal(r->module,64) || !hexadecimal(r->authorization,64) || !hexadecimal(r->local_intent,64) ||
        !hexadecimal(r->request_sha256,64) || !parent_matches(r)) return 77;
    n=snprintf(request,sizeof(request),
        "{\"attempt\":\"%s\",\"authorization_sha256\":\"%s\",\"boot\":\"%s\",\"bootstrap_operation\":\"%s\",\"device_binding_sha256\":\"%s\","
        "\"execution_enabled\":false,\"helper_sha256\":\"%s\",\"local_intent_sha256\":\"%s\",\"module_sha256\":\"%s\","
        "\"parent_dev\":%ju,\"parent_ino\":%ju,\"profile\":\"" PROFILE "\",\"schema\":1}\n",
        r->attempt,r->authorization,r->boot,r->operation,r->device,r->helper,r->local_intent,r->module,r->parent_dev,r->parent_ino);
    if (n<0 || (size_t)n>=sizeof(request)) return 77;
    sha256_init(&sha); sha256_update(&sha,domain,sizeof(domain)); sha256_update(&sha,request,(size_t)n); sha256_finish(&sha,digest);
    for (i=0;i<32;i++) { commitment[2*i]=digits[digest[i]>>4]; commitment[2*i+1]=digits[digest[i]&15]; } commitment[64]=0;
    if (strcmp(commitment,r->request_sha256)) return 77;
    memset(&action,0,sizeof(action)); action.sa_handler=SIG_IGN; sigemptyset(&action.sa_mask);
    if (sigaction(SIGPIPE,&action,NULL)) return 74;
    /* EEXIST is terminal, including empty/partial roots and other sessions.
     * Atomic mkdir is the initial no-replace barrier, not a lease takeover. */
    if (mkdirat(r->parent,ROOT_NAME,0700)) return errno==EEXIST ? 77 : 74;
    root=openat(r->parent,ROOT_NAME,O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW);
    if (root<0 || fstat(root,&pins.root) || !private_object(&pins.root,1) ||
        !pins_match(r,root,-1,&pins) || fsync(root) || fsync(r->parent) ||
        test_point(r,"after-mkdir") || !pins_match(r,root,-1,&pins) || catalogue(root,0)) goto out;
    lease=openat(root,"lease.lock",O_RDWR|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW,0600);
    if (lease<0 || fstat(lease,&pins.lease) || !private_object(&pins.lease,0) ||
        flock(lease,LOCK_EX|LOCK_NB) || !pins_match(r,root,lease,&pins) || fsync(lease) || fsync(root) ||
        fsync(r->parent) || test_point(r,"after-lease") || catalogue(root,1)) goto out;
    if (publish(r,root,lease,&pins,"intent",request,strlen(request)) || catalogue(root,2)) goto out;
    n=snprintf(receipt,sizeof(receipt),
        "{\"admission_enabled\":false,\"bootstrap_phase\":\"metadata-only-no-activation\",\"execution_enabled\":false,"
        "\"lease_dev\":%ju,\"lease_ino\":%ju,\"local_pin_ack_verified\":false,\"producer\":\"host-native-bootstrap-reference\","
        "\"profile\":\"" PROFILE "\",\"request\":%.*s,\"request_sha256\":\"%s\",\"root_dev\":%ju,\"root_ino\":%ju,\"schema\":1}\n",
        (uintmax_t)pins.lease.st_dev,(uintmax_t)pins.lease.st_ino,(int)strlen(request)-1,request,commitment,
        (uintmax_t)pins.root.st_dev,(uintmax_t)pins.root.st_ino);
    if (n<0 || (size_t)n>=sizeof(receipt) || publish(r,root,lease,&pins,"receipt",receipt,(size_t)n) ||
        catalogue(root,3) || test_point(r,"before-reply") || !pins_match(r,root,lease,&pins)) goto out;
    /* A visible valid record is not proof of the host's pin acknowledgment. */
    if (fstatat(root,"bootstrap-receipt.json",&entry,AT_SYMLINK_NOFOLLOW) || !private_object(&entry,0)) goto out;
    sha256_hex(receipt,(size_t)n,commitment);
    n=snprintf(reply,sizeof(reply),"ERIS_BOOTSTRAP_RECEIPT %s %s\n",r->operation,commitment);
    if (n<0 || (size_t)n>=sizeof(reply)) goto out;
    position=0;
    while (position<(size_t)n) {
        wrote=write(1,reply+position,(size_t)n-position);
        if (wrote<0 && errno==EINTR) continue;
        if (wrote<=0) goto out;
        position+=(size_t)wrote;
    }
    result=0;
out:
    if (lease>=0) close(lease); /* No LOCK_UN or removal of the lease inode. */
    if (root>=0) close(root);
    return result;
}

#ifdef Q3_BOOTSTRAP_HOST_TEST
static uintmax_t number(const char *text)
{
    char *end; uintmax_t value;
    if (!*text || strspn(text,"0123456789")!=strlen(text)) exit(77);
    errno=0; value=strtoumax(text,&end,10); if (errno || *end) exit(77); return value;
}
int main(int argc, char **argv)
{
    struct bootstrap_request r; uintmax_t parent,control;
    if (argc!=16 || strcmp(argv[1],"--host-bootstrap")) return 77;
    parent=number(argv[3]); control=!strcmp(argv[15],"-1") ? 0 : number(argv[15]);
    if (parent>INT_MAX || control>INT_MAX || (strcmp(argv[15],"-1") && control<3)) return 77;
    r=(struct bootstrap_request){argv[2],argv[6],argv[7],argv[8],argv[9],argv[10],argv[11],argv[12],argv[13],argv[14],
        (int)parent,control ? (int)control : -1,number(argv[4]),number(argv[5])};
    return q3_bootstrap_metadata_reference(&r);
}
#else
int main(void)
{
    static const char message[]="Disarmed native prototype: no Android/device dispatcher enabled.\n";
    ssize_t wrote=write(2,message,sizeof(message)-1); (void)wrote; return 77;
}
#endif
