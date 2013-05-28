try:
    from M2Crypto import X509, EVP, RSA, ASN1
except:
    print("Failed to load required module. Please install python M2crypto.")
    raise SystemExit
from random import randrange
from time import time


class reWiredCertificate():
    def __init__(self, (commonName)):
        self.cert = 0
        self.privateKey = 0
        self.validfor = 365  # days
        self.names = X509.X509_Name()
        self.names.C = "NA"
        self.names.ST = "NA"
        self.names.L = "NA"
        self.names.O = "re:wired"
        self.names.OU = "re:wired Server"
        self.names.CN = commonName

    def setCertValid(self, cert):
        start = ASN1.ASN1_UTCTIME()
        start.set_time(long(time()))
        end = ASN1.ASN1_UTCTIME()
        end.set_time(long(time()) + self.validfor * 24 * 60 * 60)
        cert.set_not_before(start)
        cert.set_not_after(end)
        return cert

    def createCertRequest(self, bits):
        privateKey = EVP.PKey()
        request = X509.Request()
        rsa = RSA.gen_key(bits, 65537, lambda: None)
        privateKey.assign_rsa(rsa)
        request.set_pubkey(privateKey)
        request.set_subject(self.names)
        request.sign(privateKey, 'sha1')
        return request, privateKey

    def createCA(self):
        req, privateKey = self.createCertRequest(1024)
        publicKey = req.get_pubkey()
        cert = X509.X509()
        cert.set_serial_number(randrange(0, 65537))
        cert.set_version(randrange(0, 65537))
        cert = self.setCertValid(cert)
        cert.set_issuer(mk_ca_issuer())
        cert.set_subject(cert.get_issuer())
        cert.set_pubkey(publicKey)
        cert.add_ext(X509.new_extension('basicConstraints', 'CA:TRUE'))
        cert.add_ext(X509.new_extension('subjectKeyIdentifier', cert.get_fingerprint()))
        cert.sign(privateKey, 'sha1')
        return cert, privateKey, publicKey

    def createCert(self):
        cert = X509.X509()
        cert.set_serial_number(randrange(0, 65537))
        cert.set_version(randrange(0, 65537))
        cert.set_issuer(mk_ca_issuer())
        cert = self.setCertValid(cert)
        return cert

    def createSignedCert(self):
        cacert, pk1, _ = self.createCA()
        cert_req, pk2 = self.createCertRequest(1024)
        cert = self.createCert()
        cert.set_subject(cert_req.get_subject())
        cert.set_pubkey(cert_req.get_pubkey())
        cert.sign(pk1, 'sha1')
        self.cert = cert
        self.privateKey = pk2
        self.cacert = cacert
        return 1

    def safeAsPem(self, filename):
        if not self.cert or not self.privateKey:
            return 0
        try:
            with open(filename, 'w') as f:
                f.write(self.privateKey.as_pem(None))
                f.write(self.cert.as_pem())
                f.write(self.cacert.as_pem())

        except:
            return 0
        return 1

    def loadPem(self, filename):
        try:
            rsa = RSA.load_key(filename)
            cert = X509.load_cert(filename)
        except:
            return 0
        self.privateKey = rsa
        self.cert = cert
        return 1

    def getCommonName(self):
        if not self.cert:
            return 0
        fields = str(self.cert.get_subject()).split("/")
        for afield in fields:
            if afield:
                if afield[:3] == "CN=":
                    return afield[3:]
        return 0


def mk_ca_issuer():
    issuer = X509.X509_Name()
    issuer.C = "NA"
    issuer.CN = "re:wired CA"
    issuer.ST = 'NA'
    issuer.L = 'NA'
    issuer.O = 're:wired Server'
    issuer.OU = 're:wired Server'
    return issuer
